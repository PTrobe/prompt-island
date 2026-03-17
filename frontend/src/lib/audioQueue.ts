/**
 * Audio Queue Manager — serializes game events for audience-paced playback.
 *
 * Implements the queue spec from FRONTEND_AND_STREAM.md §4:
 *   1. Display inner_thought in the Confessional sidebar.
 *   2. Pause so the audience can read it.
 *   3. Display the public message in The Hub.
 *   4. Call ElevenLabs, fetch audio, play it (speak_public only).
 *   5. Wait for audio to finish before processing the next event.
 *
 * Fallback: if TTS is not configured or fails, a duration-based delay
 * (proportional to message length) keeps the pacing readable.
 *
 * This is a module-level singleton — one queue per browser tab.
 */

import { GameEvent } from '@/types/events';
import { synthesizeSpeech, playAudioBuffer } from './elevenlabs';

type DisplayFn = (event: GameEvent) => void;
type ConfessionalFn = (thought: string | null, agentId: string, displayName: string) => void;

interface QueueItem {
  event: GameEvent;
  onDisplay: DisplayFn;
  onConfessional: ConfessionalFn;
}

class AudioQueueManager {
  private readonly queue: QueueItem[] = [];
  private processing = false;

  enqueue(event: GameEvent, onDisplay: DisplayFn, onConfessional: ConfessionalFn): void {
    this.queue.push({ event, onDisplay, onConfessional });
    if (!this.processing) this.processNext();
  }

  private async processNext(): Promise<void> {
    if (this.queue.length === 0) {
      this.processing = false;
      return;
    }
    this.processing = true;

    const { event, onDisplay, onConfessional } = this.queue.shift()!;

    // ---------------------------------------------------------------
    // Step 1: Show inner thought in Confessional (if present)
    // ---------------------------------------------------------------
    if (event.inner_thought) {
      onConfessional(event.inner_thought, event.agent_id, event.display_name);
      // Give the audience ~1.5 s to read the thought before the message appears
      await sleep(1500);
    }

    // ---------------------------------------------------------------
    // Step 2: Reveal the message in The Hub
    // ---------------------------------------------------------------
    onDisplay(event);

    // ---------------------------------------------------------------
    // Step 3: TTS for public speech; duration delay for everything else
    // ---------------------------------------------------------------
    if (event.action_type === 'speak_public' && event.message.trim()) {
      const buffer = await synthesizeSpeech(event.agent_id, event.message);
      if (buffer) {
        await playAudioBuffer(buffer);
      } else {
        // No TTS — estimate reading time from message length (~15 chars/s, min 2 s)
        await sleep(Math.max(2000, event.message.length * 67));
      }
    } else {
      // Non-speech events (votes, DMs, system) show briefly before moving on
      await sleep(event.action_type === 'system_event' ? 3000 : 1500);
    }

    // ---------------------------------------------------------------
    // Step 4: Clear Confessional and process next item
    // ---------------------------------------------------------------
    onConfessional(null, '', '');
    this.processNext();
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Singleton — imported directly by page.tsx
export const audioQueue = new AudioQueueManager();
