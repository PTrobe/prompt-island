/**
 * Main game page — the 1080p streaming canvas.
 *
 * Layout (FRONTEND_AND_STREAM.md §3):
 *   ┌──────────────────────────────────────────────────────────┐
 *   │                      STATUS BAR                          │
 *   ├──────────────────┬───────────────────────────────────────┤
 *   │  CONFESSIONAL    │            THE HUB                    │
 *   │    (30%)         │             (70%)                     │
 *   └──────────────────┴───────────────────────────────────────┘
 *
 * Event flow:
 *   WebSocket → onEvent() → audioQueue.enqueue()
 *     → onDisplay()      → setDisplayedEvents() [renders in HubChat]
 *     → onConfessional() → setConfessional()    [renders in Confessional]
 */

'use client';

import { useState, useCallback } from 'react';
import { GameEvent, ConfessionalState } from '@/types/events';
import { audioQueue } from '@/lib/audioQueue';
import { useGameStream } from '@/hooks/useGameStream';
import StatusBar from '@/components/StatusBar';
import HubChat from '@/components/HubChat';
import Confessional from '@/components/Confessional';

export default function Page() {
  const [displayedEvents, setDisplayedEvents] = useState<GameEvent[]>([]);
  const [confessional, setConfessional] = useState<ConfessionalState>({
    thought: null,
    agentId: '',
    displayName: '',
  });

  // Called by the audio queue when it's time to show an event
  const handleDisplay = useCallback((event: GameEvent) => {
    setDisplayedEvents((prev) => [...prev.slice(-150), event]);
  }, []);

  // Called by the audio queue to update the Confessional sidebar
  const handleConfessional = useCallback(
    (thought: string | null, agentId: string, displayName: string) => {
      setConfessional({ thought, agentId, displayName });
    },
    [],
  );

  // Called immediately when a WebSocket event arrives — enqueues for serialized playback
  const handleEvent = useCallback(
    (event: GameEvent) => {
      audioQueue.enqueue(event, handleDisplay, handleConfessional);
    },
    [handleDisplay, handleConfessional],
  );

  const { gameState, connected } = useGameStream(handleEvent);

  return (
    <div className="h-screen w-screen bg-black text-white flex flex-col overflow-hidden font-mono">
      <StatusBar gameState={gameState} connected={connected} />
      <div className="flex flex-1 overflow-hidden">
        <Confessional state={confessional} />
        <HubChat events={displayedEvents} />
      </div>
    </div>
  );
}
