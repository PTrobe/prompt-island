/**
 * CharacterSprite.ts — Animated character sprite with name label and speech bubble.
 *
 * Sprite sheet layout (64×120px, 4 cols × 5 rows, 16×24 px per frame):
 *   Row 0: idle    frames 0-3
 *   Row 1: walk    frames 4-7
 *   Row 2: talk    frames 8-11
 *   Row 3: react   frames 12-15
 *   Row 4: eliminated frame 16  (cols 0-3 same frame)
 */

import Phaser from 'phaser';

export type AnimState = 'idle' | 'walk' | 'talk' | 'react' | 'eliminated';

const FRAME_W = 32;
const FRAME_H = 32;

// Row indices in the sprite sheet
const ANIM_ROWS: Record<AnimState, number> = {
  idle:       0,
  walk:       1,
  talk:       2,
  react:      3,
  eliminated: 4,
};

export interface CharacterConfig {
  agentId: string;
  displayName: string;
  x: number;
  y: number;
}

export class CharacterSprite {
  readonly agentId: string;
  readonly displayName: string;

  private scene: Phaser.Scene;
  private sprite: Phaser.GameObjects.Sprite;
  private label: Phaser.GameObjects.Text;
  private bubble: Phaser.GameObjects.Container | null = null;
  private bubbleTimer: Phaser.Time.TimerEvent | null = null;
  private currentAnim: AnimState = 'idle';

  constructor(scene: Phaser.Scene, config: CharacterConfig) {
    this.scene = scene;
    this.agentId = config.agentId;
    this.displayName = config.displayName;

    // Sprite — texture key matches agentId (e.g. 'agent_01_machiavelli')
    this.sprite = scene.add.sprite(config.x, config.y, config.agentId);
    this.sprite.setOrigin(0.5, 1); // feet at (x, y)
    this.sprite.setDepth(config.y); // y-sort depth

    // Name label — small pixel font below feet
    this.label = scene.add.text(config.x, config.y + 6, config.displayName, {
      fontSize: '12px',
      color: '#ffffff',
      stroke: '#000000',
      strokeThickness: 2,
      resolution: 4,
    });
    this.label.setOrigin(0.5, 0);
    this.label.setDepth(config.y + 1);

    this._registerAnims();
    this.play('idle');
  }

  get x(): number { return this.sprite.x; }
  get y(): number { return this.sprite.y; }

  // ── Animations ────────────────────────────────────────────────────────────

  private _registerAnims(): void {
    const key = this.agentId;
    const states: AnimState[] = ['idle', 'walk', 'talk', 'react'];

    for (const state of states) {
      const animKey = `${key}_${state}`;
      if (this.scene.anims.exists(animKey)) continue;

      const row = ANIM_ROWS[state];
      const frames = this.scene.anims.generateFrameNumbers(key, {
        start: row * 4,
        end:   row * 4 + 3,
      });

      this.scene.anims.create({
        key: animKey,
        frames,
        frameRate: state === 'idle' ? 4 : state === 'walk' ? 8 : 6,
        repeat: state === 'react' ? 0 : -1,
      });
    }

    // Eliminated — single frame, no repeat
    const elimKey = `${key}_eliminated`;
    if (!this.scene.anims.exists(elimKey)) {
      this.scene.anims.create({
        key: elimKey,
        frames: this.scene.anims.generateFrameNumbers(key, { start: 16, end: 16 }),
        frameRate: 1,
        repeat: 0,
      });
    }
  }

  play(state: AnimState): void {
    if (this.currentAnim === state && this.sprite.anims.isPlaying) return;
    this.currentAnim = state;
    this.sprite.play(`${this.agentId}_${state}`);
  }

  /** Drive a specific mouth frame (0-3) directly — used by LipSyncAnalyser. */
  setTalkFrame(col: 0 | 1 | 2 | 3): void {
    this.sprite.anims.stop();
    this.sprite.setFrame(8 + col); // row 2, col 0-3
    this.currentAnim = 'talk';
  }

  // ── Movement ──────────────────────────────────────────────────────────────

  moveTo(x: number, y: number, onComplete?: () => void): void {
    this.play('walk');

    if (x < this.sprite.x) this.sprite.setFlipX(true);
    else if (x > this.sprite.x) this.sprite.setFlipX(false);

    this.scene.tweens.add({
      targets: this.sprite,
      x,
      y,
      duration: 800,
      ease: 'Linear',
      onUpdate: () => {
        this.sprite.setDepth(this.sprite.y);
      },
      onComplete: () => {
        this.play('idle');
        if (onComplete) onComplete();
      },
    });

    // Label follows at feet + 3px offset
    this.scene.tweens.add({
      targets: this.label,
      x,
      y: y + 6,
      duration: 800,
      ease: 'Linear',
      onUpdate: () => {
        this.label.setDepth(this.sprite.y + 1);
      },
    });
  }

  // ── Speech bubble ─────────────────────────────────────────────────────────

  say(text: string, durationMs = 4000): void {
    this.clearBubble();
    this.play('talk');

    // Truncate to 15 words
    const words = text.split(' ');
    const truncated = words.slice(0, 15).join(' ') + (words.length > 15 ? '…' : '');

    const padding = 8;
    const maxWidth = 180;

    const bubble = this.scene.add.container(this.sprite.x, this.sprite.y - FRAME_H - 6);
    bubble.setDepth(1000);

    const textObj = this.scene.add.text(0, 0, truncated, {
      fontSize: '12px',
      color: '#000000',
      wordWrap: { width: maxWidth - padding * 2 },
      resolution: 4,
    });
    textObj.setOrigin(0.5, 1);

    const bw = Math.min(textObj.width + padding * 2, maxWidth);
    const bh = textObj.height + padding * 2;

    const bg = this.scene.add.graphics();
    bg.fillStyle(0xfffde7, 1);
    bg.strokeRect(-bw / 2, -bh, bw, bh);
    bg.fillRect(-bw / 2, -bh, bw, bh);

    bubble.add([bg, textObj]);
    this.bubble = bubble;

    this.bubbleTimer = this.scene.time.delayedCall(durationMs, () => {
      this.clearBubble();
      this.play('idle');
    });
  }

  clearBubble(): void {
    if (this.bubbleTimer) {
      this.bubbleTimer.remove();
      this.bubbleTimer = null;
    }
    if (this.bubble) {
      this.bubble.destroy();
      this.bubble = null;
    }
  }

  // ── React animation ───────────────────────────────────────────────────────

  react(onComplete?: () => void): void {
    this.play('react');
    this.sprite.once(Phaser.Animations.Events.ANIMATION_COMPLETE, () => {
      this.play('idle');
      if (onComplete) onComplete();
    });
  }

  // ── Elimination ───────────────────────────────────────────────────────────

  eliminate(): void {
    this.clearBubble();
    this.play('eliminated');
    this.scene.tweens.add({
      targets: this.sprite,
      alpha: 0,
      x: this.sprite.x + (Math.random() > 0.5 ? 40 : -40),
      duration: 2000,
      ease: 'Power2',
    });
    this.scene.tweens.add({
      targets: this.label,
      alpha: 0,
      duration: 2000,
    });
  }

  // ── Bubble position sync (call each frame) ────────────────────────────────

  update(): void {
    if (this.bubble) {
      this.bubble.setPosition(this.sprite.x, this.sprite.y - FRAME_H - 6);
    }
  }

  destroy(): void {
    this.clearBubble();
    this.sprite.destroy();
    this.label.destroy();
  }
}
