/**
 * LipSyncAnalyser.ts — Drives character mouth frames from live audio amplitude.
 *
 * Attaches a Web Audio AnalyserNode to the ElevenLabs audio buffer and
 * exposes getMouthState() which maps RMS amplitude → one of four talk frames.
 *
 * Usage:
 *   const analyser = new LipSyncAnalyser(audioContext)
 *   analyser.connectSource(sourceNode)
 *   // In Phaser update():
 *   const state = analyser.getMouthState()  // 0-3 → column in TALK row
 *   sprite.setFrame(8 + state)              // row 2 = frames 8-11
 *   // When audio ends:
 *   analyser.disconnect()
 */

export type MouthState = 0 | 1 | 2 | 3; // CLOSED | SLIGHT | OPEN | WIDE

// RMS thresholds — tuned for ElevenLabs output levels
const THRESH_SLIGHT = 0.02;
const THRESH_OPEN   = 0.06;
const THRESH_WIDE   = 0.12;

export class LipSyncAnalyser {
  private analyser: AnalyserNode;
  private buffer: Float32Array<ArrayBuffer>;
  private _connected = false;

  constructor(ctx: AudioContext) {
    this.analyser = ctx.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.smoothingTimeConstant = 0.4;
    this.buffer = new Float32Array(this.analyser.fftSize) as Float32Array<ArrayBuffer>;
  }

  connectSource(source: AudioNode): void {
    source.connect(this.analyser);
    this._connected = true;
  }

  getMouthState(): MouthState {
    if (!this._connected) return 0;

    this.analyser.getFloatTimeDomainData(this.buffer);

    // RMS amplitude
    let sum = 0;
    for (let i = 0; i < this.buffer.length; i++) {
      sum += this.buffer[i] * this.buffer[i];
    }
    const rms = Math.sqrt(sum / this.buffer.length);

    if (rms >= THRESH_WIDE)   return 3;
    if (rms >= THRESH_OPEN)   return 2;
    if (rms >= THRESH_SLIGHT) return 1;
    return 0;
  }

  get connected(): boolean {
    return this._connected;
  }

  disconnect(): void {
    try {
      this.analyser.disconnect();
    } catch {
      // already disconnected
    }
    this._connected = false;
  }
}
