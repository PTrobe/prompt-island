/**
 * useGameStream — WebSocket connection to the Prompt Island backend.
 *
 * On mount, connects to WS_URL (/ws). On each message, parses the JSON
 * and calls onEvent(). Automatically reconnects on disconnect (3 s delay).
 *
 * Also polls /state every 10 s for contestant standings and current phase
 * (the WebSocket only carries ChatLog events, not GameState changes).
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { GameEvent, GameState } from '@/types/events';

const WS_URL  = process.env.NEXT_PUBLIC_API_WS_URL  ?? 'ws://localhost:8000/ws';
const HTTP_URL = process.env.NEXT_PUBLIC_API_HTTP_URL ?? 'http://localhost:8000';

interface UseGameStreamResult {
  gameState: GameState | null;
  connected: boolean;
}

export function useGameStream(
  onEvent: (event: GameEvent) => void,
): UseGameStreamResult {
  const [gameState, setGameState]   = useState<GameState | null>(null);
  const [connected, setConnected]   = useState(false);
  const onEventRef                  = useRef(onEvent);

  // Keep ref current so the WebSocket closure doesn't go stale
  useEffect(() => { onEventRef.current = onEvent; }, [onEvent]);

  // Poll /state for contestant standings + current phase
  useEffect(() => {
    const fetchState = () => {
      fetch(`${HTTP_URL}/state`)
        .then((r) => r.json())
        .then((data: GameState) => setGameState(data))
        .catch(() => {}); // silently ignore — backend may not be up yet
    };
    fetchState();
    const id = setInterval(fetchState, 10_000);
    return () => clearInterval(id);
  }, []);

  // WebSocket connection with auto-reconnect
  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let destroyed = false;

    function connect() {
      if (destroyed) return;
      ws = new WebSocket(WS_URL);

      ws.onopen  = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!destroyed) reconnectTimeout = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();

      ws.onmessage = (e: MessageEvent) => {
        try {
          const event: GameEvent = JSON.parse(e.data as string);
          onEventRef.current(event);
        } catch {
          // Malformed JSON — skip
        }
      };
    }

    connect();

    return () => {
      destroyed = true;
      clearTimeout(reconnectTimeout);
      ws?.close();
    };
  }, []); // stable — no deps; onEvent accessed via ref

  return { gameState, connected };
}
