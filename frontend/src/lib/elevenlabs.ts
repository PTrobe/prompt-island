/**
 * ElevenLabs TTS client.
 *
 * Each agent maps to a unique ElevenLabs voice_id, configurable via
 * NEXT_PUBLIC_VOICE_* environment variables. If NEXT_PUBLIC_ELEVENLABS_API_KEY
 * is not set, synthesizeSpeech() returns null and the audio queue falls back
 * to a duration-based delay so the UI still works without TTS.
 */

const API_BASE = 'https://api.elevenlabs.io/v1';

// Default voice IDs from the ElevenLabs free voice library.
// Override per-agent with NEXT_PUBLIC_VOICE_<AGENT_SUFFIX> env vars.
export const VOICE_MAP: Record<string, string> = {
  agent_01_machiavelli: process.env.NEXT_PUBLIC_VOICE_MACHIAVELLI ?? '21m00Tcm4TlvDq8ikWAM', // Rachel
  agent_02_chaos:       process.env.NEXT_PUBLIC_VOICE_CHAOS       ?? 'AZnzlk1XvdvUeBnXmlld', // Domi
  agent_03_empath:      process.env.NEXT_PUBLIC_VOICE_EMPATH      ?? 'EXAVITQu4vr4xnSDxMaL', // Bella
  agent_04_pedant:      process.env.NEXT_PUBLIC_VOICE_PEDANT      ?? 'ErXwobaYiN019PkySvjV', // Antoni
  agent_05_paranoid:    process.env.NEXT_PUBLIC_VOICE_PARANOID    ?? 'MF3mGyEYCl7XYWbV9V6O', // Elli
  agent_06_floater:     process.env.NEXT_PUBLIC_VOICE_FLOATER     ?? 'TxGEqnHWrfWFTfGW9XjX', // Josh
};

/**
 * Synthesize speech for an agent's message.
 * Returns an ArrayBuffer on success, or null if TTS is unconfigured or the
 * call fails (caller should fall back to a timed delay).
 */
export async function synthesizeSpeech(
  agentId: string,
  text: string,
): Promise<ArrayBuffer | null> {
  const apiKey = process.env.NEXT_PUBLIC_ELEVENLABS_API_KEY;
  if (!apiKey || !text.trim()) return null;

  const voiceId = VOICE_MAP[agentId] ?? VOICE_MAP['agent_06_floater'];

  try {
    const response = await fetch(`${API_BASE}/text-to-speech/${voiceId}`, {
      method: 'POST',
      headers: {
        'xi-api-key': apiKey,
        'Content-Type': 'application/json',
        'Accept': 'audio/mpeg',
      },
      body: JSON.stringify({
        text,
        model_id: 'eleven_monolingual_v1',
        voice_settings: { stability: 0.5, similarity_boost: 0.75 },
      }),
    });

    if (!response.ok) {
      console.warn(`ElevenLabs TTS failed: ${response.status} ${response.statusText}`);
      return null;
    }

    return response.arrayBuffer();
  } catch (err) {
    console.warn('ElevenLabs TTS error:', err);
    return null;
  }
}

/**
 * Decode and play an audio ArrayBuffer via the Web Audio API.
 * Resolves when playback completes (or immediately on decode error).
 *
 * onSource(ctx, source) — called just before playback starts so callers can
 * attach an AnalyserNode for lip-sync.
 */
export function playAudioBuffer(
  buffer: ArrayBuffer,
  onSource?: (ctx: AudioContext, source: AudioBufferSourceNode) => void,
): Promise<void> {
  return new Promise((resolve) => {
    try {
      const audioCtx = new AudioContext();
      audioCtx.decodeAudioData(
        buffer,
        (decoded) => {
          const source = audioCtx.createBufferSource();
          source.buffer = decoded;
          source.connect(audioCtx.destination);
          if (onSource) onSource(audioCtx, source);
          source.onended = () => resolve();
          source.start(0);
        },
        () => resolve(),
      );
    } catch {
      resolve();
    }
  });
}
