/**
 * IslandScene.ts — Main Phaser scene: tilemap + 6 characters placed on island.
 *
 * Phase 5b: static placement at shelter (all agents start there).
 * Phase 5c will add walk-to-location triggered by WebSocket events.
 */

import Phaser from 'phaser';
import { CharacterSprite } from '../sprites/CharacterSprite';
import { LOCATIONS, LocationId, phaseToLocation } from '../map/IslandMap';

// The 6 contestants — must match backend agent_ids exactly
const AGENTS = [
  { agentId: 'agent_01_machiavelli', displayName: 'Alex'   },
  { agentId: 'agent_02_chaos',       displayName: 'Jordan' },
  { agentId: 'agent_03_empath',      displayName: 'Sam'    },
  { agentId: 'agent_04_pedant',      displayName: 'Morgan' },
  { agentId: 'agent_05_paranoid',    displayName: 'Casey'  },
  { agentId: 'agent_06_floater',     displayName: 'Riley'  },
];

export class IslandScene extends Phaser.Scene {
  private characters: Map<string, CharacterSprite> = new Map();
  private agentLocations: Map<string, LocationId> = new Map();

  constructor() {
    super({ key: 'IslandScene' });
  }

  // ── Asset loading ─────────────────────────────────────────────────────────

  preload(): void {
    // Tilemap + tileset
    this.load.tilemapTiledJSON('island_map', '/maps/island.json');
    this.load.image('tiles', '/tiles/island_tileset.png');

    // Character sprite sheets (64×120, frameWidth=16, frameHeight=24)
    for (const agent of AGENTS) {
      this.load.spritesheet(agent.agentId, `/sprites/${agent.agentId}_sheet.png`, {
        frameWidth:  64,
        frameHeight: 96,
      });
    }
  }

  // ── Scene creation ────────────────────────────────────────────────────────

  create(): void {
    // ── Tilemap ──────────────────────────────────────────────────────────────
    const map = this.make.tilemap({ key: 'island_map' });
    const tileset = map.addTilesetImage('island_tileset', 'tiles');

    if (!tileset) {
      console.error('[IslandScene] Failed to load tileset — check island.json tileset name');
      return;
    }

    map.createLayer('terrain', tileset, 0, 0);
    map.createLayer('objects', tileset, 0, 0);

    // ── Camera ───────────────────────────────────────────────────────────────
    const cam = this.cameras.main;
    cam.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
    cam.setZoom(1);

    // Start focused on the shelter where all agents begin
    const shelterLoc = LOCATIONS.shelter;
    cam.centerOn(shelterLoc.cx, shelterLoc.cy);

    // ── Characters ───────────────────────────────────────────────────────────
    // Place all agents at shelter formation spots
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

    // ── Expose scene on window for React bridge ───────────────────────────────
    (window as any).__islandScene = this;
  }

  // ── Per-frame update ──────────────────────────────────────────────────────

  update(): void {
    Array.from(this.characters.values()).forEach((char) => char.update());
  }

  // ── Public API (called by React/WebSocket bridge) ─────────────────────────

  /**
   * Move a single agent to a new location.
   * Stagger is applied by the caller (150ms per agent for group moves).
   */
  moveAgentTo(agentId: string, locationId: LocationId, spotIndex?: number): void {
    const char = this.characters.get(agentId);
    if (!char) return;

    const location = LOCATIONS[locationId];
    const idx = spotIndex ?? this._nextFreeSpot(locationId, agentId);
    const spot = location.spots[idx] ?? { x: location.cx, y: location.cy };

    this.agentLocations.set(agentId, locationId);
    char.moveTo(spot.x, spot.y);
  }

  /** Move all active agents to a location, staggered 150ms apart. */
  moveAllTo(locationId: LocationId): void {
    Array.from(this.characters.keys()).forEach((agentId, i) => {
      this.time.delayedCall(i * 150, () => this.moveAgentTo(agentId, locationId, i));
    });
  }

  /** Show speech bubble + trigger talk animation for an agent. */
  agentSpeak(agentId: string, text: string, durationMs = 4000): void {
    this.characters.get(agentId)?.say(text, durationMs);
  }

  /** Trigger react anim (e.g. vote received). */
  agentReact(agentId: string): void {
    this.characters.get(agentId)?.react();
  }

  /** Play elimination sequence for an agent. */
  eliminateAgent(agentId: string): void {
    this.characters.get(agentId)?.eliminate();
  }

  /**
   * Zoom camera to a location, then ease back.
   * zoomLevel default 3, hold for holdMs, then return to zoom 2.
   */
  focusCamera(locationId: LocationId, zoomLevel = 2, holdMs = 3000): void {
    const loc = LOCATIONS[locationId];
    const cam = this.cameras.main;

    cam.pan(loc.cx, loc.cy, 600, 'Power2');
    cam.zoomTo(zoomLevel, 600, 'Linear', false, (_cam: Phaser.Cameras.Scene2D.Camera, progress: number) => {
      if (progress === 1) {
        this.time.delayedCall(holdMs, () => {
          cam.pan(cam.midPoint.x, cam.midPoint.y, 600, 'Power2');
          cam.zoomTo(2, 600);
        });
      }
    });
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  private _nextFreeSpot(locationId: LocationId, agentId: string): number {
    const location = LOCATIONS[locationId];
    const occupied = new Set<number>();

    Array.from(this.agentLocations.entries()).forEach(([id, locId]) => {
      if (id !== agentId && locId === locationId) {
        // Approximate which spot they're at
        const char = this.characters.get(id);
        if (char) {
          for (let s = 0; s < location.spots.length; s++) {
            const sp = location.spots[s];
            if (Math.abs(char.x - sp.x) < 4 && Math.abs(char.y - sp.y) < 4) {
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
