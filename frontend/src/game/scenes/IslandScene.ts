/**
 * IslandScene.ts — Main Phaser scene: tilemap, 6 characters, overlays.
 *
 * Phase 5c/d/e/f/g:
 *   - Agent movement triggered by phase_change WebSocket events
 *   - Camera focus on active speaker (5d)
 *   - LipSync driven by AnalyserNode from ElevenLabs audio (5e)
 *   - Confessional zoom sequence + elimination walk-off (5f)
 *   - NIGHT_IDLE dark overlay, WAITING indicator (5g)
 */

import Phaser from 'phaser';
import { CharacterSprite } from '../sprites/CharacterSprite';
import { LOCATIONS, LocationId } from '../map/IslandMap';
import { LipSyncAnalyser } from '../audio/LipSyncAnalyser';

const AGENTS = [
  { agentId: 'agent_01_machiavelli', displayName: 'Alex'   },
  { agentId: 'agent_02_chaos',       displayName: 'Jordan' },
  { agentId: 'agent_03_empath',      displayName: 'Sam'    },
  { agentId: 'agent_04_pedant',      displayName: 'Morgan' },
  { agentId: 'agent_05_paranoid',    displayName: 'Casey'  },
  { agentId: 'agent_06_floater',     displayName: 'Riley'  },
];

// Seconds of inactivity before WAITING indicator appears
const WAITING_TIMEOUT_S = 90;

export class IslandScene extends Phaser.Scene {
  private characters: Map<string, CharacterSprite> = new Map();
  private agentLocations: Map<string, LocationId> = new Map();

  // ── Overlays ──────────────────────────────────────────────────────────────
  private nightOverlay!:    Phaser.GameObjects.Rectangle;
  private nightText!:       Phaser.GameObjects.Text;
  private waitingText!:     Phaser.GameObjects.Text;
  private _nightActive     = false;
  private _waitingActive   = false;
  private _lastEventTime   = 0;

  // ── Lip-sync ──────────────────────────────────────────────────────────────
  private _lipSyncAnalyser:  LipSyncAnalyser | null = null;
  private _lipSyncAgentId:   string | null = null;
  private _lipSyncFrame      = 0;

  constructor() {
    super({ key: 'IslandScene' });
  }

  // ── Asset loading ─────────────────────────────────────────────────────────

  preload(): void {
    this.load.tilemapTiledJSON('island_map', '/maps/island.json');
    this.load.image('tiles', '/tiles/island_tileset.png');

    for (const agent of AGENTS) {
      this.load.spritesheet(agent.agentId, `/sprites/${agent.agentId}_sheet.png`, {
        frameWidth:  32,
        frameHeight: 32,
      });
    }
  }

  // ── Scene creation ────────────────────────────────────────────────────────

  create(): void {
    const map = this.make.tilemap({ key: 'island_map' });
    const tileset = map.addTilesetImage('island_tileset', 'tiles');

    if (!tileset) {
      console.error('[IslandScene] Failed to load tileset');
      return;
    }

    map.createLayer('terrain', tileset, 0, 0);
    map.createLayer('objects', tileset, 0, 0);

    const W = map.widthInPixels;
    const H = map.heightInPixels;

    // ── Camera ───────────────────────────────────────────────────────────────
    const cam = this.cameras.main;
    cam.setBounds(0, 0, W, H);
    cam.setZoom(2);
    cam.centerOn(LOCATIONS.shelter.cx, LOCATIONS.shelter.cy);

    // ── Characters ───────────────────────────────────────────────────────────
    const shelter = LOCATIONS.shelter;
    AGENTS.forEach((agent, i) => {
      const spot = shelter.spots[i] ?? { x: shelter.cx, y: shelter.cy };
      const char = new CharacterSprite(this, {
        agentId:     agent.agentId,
        displayName: agent.displayName,
        x: spot.x,
        y: spot.y,
      });
      this.characters.set(agent.agentId, char);
      this.agentLocations.set(agent.agentId, 'shelter');
    });

    // ── NIGHT_IDLE overlay ────────────────────────────────────────────────────
    // Fixed to camera — created at map centre, camera-scrollFixed via setScrollFactor
    this.nightOverlay = this.add.rectangle(W / 2, H / 2, W, H, 0x0a1628, 0.65);
    this.nightOverlay.setDepth(500).setScrollFactor(0).setVisible(false);
    // Reposition to fill canvas (scrollFactor=0 means position is in screen space)
    this.nightOverlay.setPosition(this.scale.width / 2, this.scale.height / 2);
    this.nightOverlay.setSize(this.scale.width, this.scale.height);

    this.nightText = this.add.text(
      this.scale.width / 2,
      this.scale.height / 2,
      'Night falls on the island...',
      { fontSize: '18px', color: '#8ab4d4', stroke: '#000', strokeThickness: 3, resolution: 4 },
    );
    this.nightText.setOrigin(0.5).setDepth(501).setScrollFactor(0).setVisible(false);

    // ── WAITING indicator ─────────────────────────────────────────────────────
    this.waitingText = this.add.text(
      this.scale.width / 2,
      this.scale.height - 40,
      '⏳ The game is thinking...',
      { fontSize: '12px', color: '#aaaaaa', stroke: '#000', strokeThickness: 2, resolution: 4 },
    );
    this.waitingText.setOrigin(0.5).setDepth(502).setScrollFactor(0).setVisible(false);

    this._lastEventTime = this.time.now;

    (window as any).__islandScene = this;
  }

  // ── Per-frame update ──────────────────────────────────────────────────────

  update(): void {
    Array.from(this.characters.values()).forEach((char) => char.update());

    // ── Lip-sync ─────────────────────────────────────────────────────────────
    if (this._lipSyncAnalyser?.connected && this._lipSyncAgentId) {
      const mouthState = this._lipSyncAnalyser.getMouthState();
      if (mouthState !== this._lipSyncFrame) {
        this._lipSyncFrame = mouthState;
        // Frame 8-11 = row 2 (TALK row), col = mouthState
        this.characters.get(this._lipSyncAgentId)?.setTalkFrame(mouthState);
      }
    } else if (this._lipSyncAgentId && !this._lipSyncAnalyser?.connected) {
      // Audio ended — return to idle
      this.characters.get(this._lipSyncAgentId)?.play('idle');
      this._lipSyncAgentId = null;
    }

    // ── WAITING indicator ─────────────────────────────────────────────────────
    const idleSecs = (this.time.now - this._lastEventTime) / 1000;
    const shouldWait = idleSecs > WAITING_TIMEOUT_S;
    if (shouldWait !== this._waitingActive) {
      this._waitingActive = shouldWait;
      this.waitingText.setVisible(shouldWait);
      if (shouldWait) {
        this.tweens.add({
          targets: this.waitingText,
          alpha: { from: 1, to: 0.3 },
          duration: 1200,
          yoyo: true,
          repeat: -1,
        });
      } else {
        this.tweens.killTweensOf(this.waitingText);
        this.waitingText.setAlpha(1);
      }
    }
  }

  // ── Public API ────────────────────────────────────────────────────────────

  /** Called by page.tsx on every WebSocket event to reset the WAITING timer. */
  notifyEvent(): void {
    this._lastEventTime = this.time.now;
    if (this._waitingActive) {
      this._waitingActive = false;
      this.waitingText.setVisible(false);
      this.tweens.killTweensOf(this.waitingText);
    }
  }

  moveAgentTo(agentId: string, locationId: LocationId, spotIndex?: number): void {
    const char = this.characters.get(agentId);
    if (!char) return;
    const location = LOCATIONS[locationId];
    const idx = spotIndex ?? this._nextFreeSpot(locationId, agentId);
    const spot = location.spots[idx] ?? { x: location.cx, y: location.cy };
    this.agentLocations.set(agentId, locationId);
    char.moveTo(spot.x, spot.y);
  }

  moveAllTo(locationId: LocationId): void {
    Array.from(this.characters.keys()).forEach((agentId, i) => {
      this.time.delayedCall(i * 150, () => this.moveAgentTo(agentId, locationId, i));
    });
  }

  agentSpeak(agentId: string, text: string, durationMs = 4000): void {
    this.characters.get(agentId)?.say(text, durationMs);
    // Zoom in to speaker for the duration of speech then pull back to base zoom
    this.focusOnAgent(agentId, 3.5, durationMs);
  }

  agentReact(agentId: string): void {
    this.characters.get(agentId)?.react();
  }

  eliminateAgent(agentId: string): void {
    const char = this.characters.get(agentId);
    if (!char) return;
    // Zoom in on the eliminated agent, then play exit
    this.focusOnAgent(agentId, 4, 4500);
    this.time.delayedCall(500, () => char.eliminate());
  }

  /** Zoom camera to a location, hold, then pull back to base zoom (2). */
  focusCamera(locationId: LocationId, zoomLevel = 3, holdMs = 3000): void {
    const loc = LOCATIONS[locationId];
    const cam = this.cameras.main;
    cam.pan(loc.cx, loc.cy, 600, 'Power2');
    cam.zoomTo(zoomLevel, 600, 'Linear', false, (_c: Phaser.Cameras.Scene2D.Camera, p: number) => {
      if (p === 1) {
        this.time.delayedCall(holdMs, () => cam.zoomTo(2, 600));
      }
    });
  }

  /** Zoom camera to a specific agent's world position. */
  focusOnAgent(agentId: string, zoomLevel = 3.5, holdMs = 3000): void {
    const char = this.characters.get(agentId);
    if (!char) return;
    const cam = this.cameras.main;
    cam.pan(char.x, char.y, 400, 'Power2');
    cam.zoomTo(zoomLevel, 400, 'Linear', false, (_c: Phaser.Cameras.Scene2D.Camera, p: number) => {
      if (p === 1) {
        this.time.delayedCall(holdMs, () => cam.zoomTo(2, 500));
      }
    });
  }

  /**
   * Confessional sequence:
   * zoom to hut → show bubble → zoom back.
   */
  confessionalSequence(agentId: string, text: string): void {
    this.moveAgentTo(agentId, 'confessional_hut', 0);
    this.time.delayedCall(900, () => {
      this.focusCamera('confessional_hut', 4, 5000);
      this.time.delayedCall(600, () => {
        this.characters.get(agentId)?.say(text, 4500);
      });
    });
  }

  /** Activate NIGHT_IDLE dark overlay. */
  setNightMode(active: boolean): void {
    if (this._nightActive === active) return;
    this._nightActive = active;
    this.nightOverlay.setVisible(active);
    this.nightText.setVisible(active);
    if (active) {
      this.nightText.setAlpha(0);
      this.tweens.add({ targets: this.nightText, alpha: 1, duration: 2000 });
    }
  }

  /** Attach LipSyncAnalyser for an agent's TTS audio. */
  startLipSync(agentId: string, ctx: AudioContext, source: AudioBufferSourceNode): void {
    if (this._lipSyncAnalyser) this._lipSyncAnalyser.disconnect();
    this._lipSyncAnalyser = new LipSyncAnalyser(ctx);
    this._lipSyncAnalyser.connectSource(source);
    this._lipSyncAgentId = agentId;
    this._lipSyncFrame = 0;
    source.onended = () => {
      this._lipSyncAnalyser?.disconnect();
      this._lipSyncAnalyser = null;
    };
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  private _nextFreeSpot(locationId: LocationId, agentId: string): number {
    const location = LOCATIONS[locationId];
    const occupied = new Set<number>();
    Array.from(this.agentLocations.entries()).forEach(([id, locId]) => {
      if (id !== agentId && locId === locationId) {
        const char = this.characters.get(id);
        if (char) {
          for (let s = 0; s < location.spots.length; s++) {
            const sp = location.spots[s];
            if (Math.abs(char.x - sp.x) < 8 && Math.abs(char.y - sp.y) < 8) {
              occupied.add(s);
              break;
            }
          }
        }
      }
    });
    for (let s = 0; s < location.spots.length; s++) {
      if (!occupied.has(s)) return s;
    }
    return 0;
  }
}
