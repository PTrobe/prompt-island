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
 *   └────────────────────────────────┴────────────────────────┘
 *
 * Event routing:
 *   phase_change   → moveAllTo + focusCamera + night mode toggle
 *   speak_public   → agentSpeak + focusOnAgent + lip-sync
 *   speak_private  → confessionalSequence (when inner_thought present)
 *   vote           → agentReact
 *   elimination    → eliminateAgent + focusCamera
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
import { phaseToLocation } from '@/game/map/IslandMap';
import type { LocationId } from '@/game/map/IslandMap';

const PhaserGame = dynamic(() => import('@/game/PhaserGame'), { ssr: false });

export default function Page() {
  const [displayedEvents, setDisplayedEvents] = useState<GameEvent[]>([]);
  const [confessional, setConfessional] = useState<ConfessionalState>({
    thought: null, agentId: '', displayName: '',
  });
  const sceneRef    = useRef<IslandScene | null>(null);
  const lastPhaseRef = useRef<string>('');

  const handleSceneReady = useCallback((scene: IslandScene) => {
    sceneRef.current = scene;

    // Wire lip-sync: when ElevenLabs plays audio, pipe it through the scene
    audioQueue.setLipSyncCallback((agentId, ctx, source) => {
      scene.startLipSync(agentId, ctx, source);
    });
  }, []);

  const handleDisplay = useCallback((event: GameEvent) => {
    setDisplayedEvents((prev) => [...prev.slice(-150), event]);

    const scene = sceneRef.current;
    if (!scene) return;

    // Reset WAITING timer on every event
    scene.notifyEvent();

    // ── Phase change detection ──────────────────────────────────────────────
    // Every event carries a phase field — detect transitions from any event type
    if (event.phase && event.phase !== lastPhaseRef.current) {
      lastPhaseRef.current = event.phase;
      const locId = phaseToLocation(event.phase) as LocationId;
      scene.moveAllTo(locId);
      scene.focusCamera(locId);
      scene.setNightMode(event.phase === 'night_consolidation');
    }

    // ── Action-specific routing ─────────────────────────────────────────────
    switch (event.action_type) {
      case 'speak_public':
        if (event.agent_id && event.message) {
          scene.agentSpeak(event.agent_id, event.message);
        }
        break;

      case 'speak_private':
        // Inner thoughts go to confessional zoom sequence on the island
        if (event.inner_thought && event.agent_id) {
          scene.confessionalSequence(event.agent_id, event.inner_thought);
        }
        break;

      case 'vote':
        if (event.agent_id) scene.agentReact(event.agent_id);
        if (event.target_agent_id) {
          // Target also reacts (worried)
          scene.time?.delayedCall(800, () => scene.agentReact(event.target_agent_id!));
        }
        break;

      case 'elimination':
        if (event.agent_id) {
          scene.eliminateAgent(event.agent_id);
        }
        break;

      case 'phase_change':
        // Already handled above via phase field detection — no extra action needed
        break;
    }
  }, []);

  const handleConfessional = useCallback(
    (thought: string | null, agentId: string, displayName: string) => {
      setConfessional({ thought, agentId, displayName });
    },
    [],
  );

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
        {/* Left: Phaser island */}
        <div className="relative flex-1 bg-[#1a3a5c] overflow-hidden">
          <PhaserGame onSceneReady={handleSceneReady} />

          {confessional.thought && (
            <div className="absolute inset-0 pointer-events-none">
              <Confessional state={confessional} />
            </div>
          )}
        </div>

        {/* Right: chat log */}
        <div className="w-[300px] border-l border-neutral-800 overflow-hidden flex flex-col">
          <HubChat events={displayedEvents} />
        </div>
      </div>
    </div>
  );
}
