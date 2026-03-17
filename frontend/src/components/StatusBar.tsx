/**
 * StatusBar — top bar showing day, phase, and contestant standings.
 *
 * Layout (per FRONTEND_AND_STREAM.md §3):
 *   [● LIVE]  Day 3 — Morning Chat   [Alex] [Jordan✗] [Sam] [Morgan] [Casey] [Riley]
 */

import { GameState } from '@/types/events';

interface Props {
  gameState: GameState | null;
  connected: boolean;
}

const PHASE_LABELS: Record<string, string> = {
  morning_chat:       'Morning Chat',
  challenge:          'Challenge',
  scramble:           'The Scramble',
  tribal_council:     'Tribal Council',
  night_consolidation: 'Night Consolidation',
};

export default function StatusBar({ gameState, connected }: Props) {
  const phase = gameState?.current_phase
    ? (PHASE_LABELS[gameState.current_phase] ?? gameState.current_phase)
    : '—';

  return (
    <div className="flex items-center gap-6 px-6 py-2 bg-zinc-950 border-b border-zinc-800 text-sm shrink-0">
      {/* Live indicator */}
      <div className="flex items-center gap-2">
        <span
          className={`w-2 h-2 rounded-full ${connected ? 'bg-red-500 animate-pulse' : 'bg-zinc-600'}`}
        />
        <span className={connected ? 'text-red-400 font-bold' : 'text-zinc-500'}>
          {connected ? 'LIVE' : 'OFFLINE'}
        </span>
      </div>

      {/* Day / Phase */}
      <div className="text-zinc-300">
        <span className="text-zinc-500">Day </span>
        <span className="text-white font-bold">{gameState?.current_day ?? '—'}</span>
        <span className="text-zinc-500 mx-2">·</span>
        <span className="text-amber-400">{phase}</span>
      </div>

      {/* Contestant pills */}
      <div className="flex items-center gap-2 ml-auto">
        {gameState?.contestants.map((c) => (
          <span
            key={c.agent_id}
            className={`px-2 py-0.5 rounded text-xs font-mono ${
              c.is_eliminated
                ? 'bg-zinc-900 text-zinc-600 line-through'
                : 'bg-zinc-800 text-zinc-200'
            }`}
          >
            {c.display_name}
            {c.is_eliminated && ` (D${c.eliminated_on_day})`}
          </span>
        )) ?? (
          <span className="text-zinc-600 text-xs">Waiting for game…</span>
        )}
      </div>
    </div>
  );
}
