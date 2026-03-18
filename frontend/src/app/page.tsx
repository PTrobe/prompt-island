/**
 * Main game page — 1920×1080 OBS capture canvas.
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────────────┐
 *   │                    STATUS BAR (top)                      │
 *   ├────────────────────────────────┬────────────────────────┤
 *   │                                │  CHAT LOG (right)      │
 *   │        PHASER ISLAND           │  ~300px                │
 *   │         (fills left)           │                        │
 *   │                                │                        │
 *   └────────────────────────────────┴────────────────────────┘
 *
 * Confessional still renders as an overlay within the Phaser canvas area
 * when an inner_thought arrives.
 *
 * Event flow:
 *   WebSocket → onEvent() → audioQueue.enqueue()
 *     → onDisplay()      → setDisplayedEvents() [chat log]
 *     → onConfessional() → setConfessional()    [confessional overlay]
 *   WebSocket → island events → islandScene methods
 */

'use client';

import { useState, useCallback, useRef } from 'react';
import dynamic from 'next/dynamic';
import { GameEvent, ConfessionalState } from '@/types/events';
import { audioQueue } from '@/lib/audioQueue';
import { useGameStream } from '@/hooks/useGameStream';
import StatusBar from '@/components/StatusBar';
import HubChat from '@/components/HubChat';
import Confessional from '@/components/Confessional';
import type { IslandScene } from '@/game/scenes/IslandScene';
import type { LocationId } from '@/game/map/IslandMap';
import { phaseToLocation } from '@/game/map/IslandMap';

// Phaser must not run on the server — SSR=false is required
const PhaserGame = dynamic(() => import('@/game/PhaserGame'), { ssr: false });

export default function Page() {
  const [displayedEvents, setDisplayedEvents] = useState<GameEvent[]>([]);
  const [confessional, setConfessional] = useState<ConfessionalState>({
    thought: null,
    agentId: '',
    displayName: '',
  });
  const sceneRef = useRef<IslandScene | null>(null);

  const handleSceneReady = useCallback((scene: IslandScene) => {
    sceneRef.current = scene;
  }, []);

  // Called by the audio queue when it's time to show an event
  const handleDisplay = useCallback((event: GameEvent) => {
    setDisplayedEvents((prev) => [...prev.slice(-150), event]);

    // Drive island visuals from game events
    const scene = sceneRef.current;
    if (!scene) return;

    if (event.action_type === 'speak_public' && event.agent_id) {
      scene.agentSpeak(event.agent_id, event.message);
    }
    if (event.action_type === 'vote' && event.agent_id) {
      scene.agentReact(event.agent_id);
    }
    if (event.action_type === 'elimination' && event.agent_id) {
      scene.eliminateAgent(event.agent_id);
    }
    if (event.action_type === 'phase_change' && event.phase) {
      const locId = phaseToLocation(event.phase) as LocationId;
      scene.moveAllTo(locId);
      scene.focusCamera(locId);
    }
  }, []);

  // Called by the audio queue to update the Confessional overlay
  const handleConfessional = useCallback(
    (thought: string | null, agentId: string, displayName: string) => {
      setConfessional({ thought, agentId, displayName });
    },
    [],
  );

  // Called immediately when a WebSocket event arrives
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
        {/* Left: Phaser island — fills available space */}
        <div className="relative flex-1 bg-[#1a3a5c] overflow-hidden">
          <PhaserGame onSceneReady={handleSceneReady} />

          {/* Confessional overlays the island when active */}
          {confessional.thought && (
            <div className="absolute inset-0 pointer-events-none">
              <Confessional state={confessional} />
            </div>
          )}
        </div>

        {/* Right: chat log panel */}
        <div className="w-[300px] border-l border-neutral-800 overflow-hidden flex flex-col">
          <HubChat events={displayedEvents} />
        </div>
      </div>
    </div>
  );
}
