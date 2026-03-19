'use client';

/**
 * FinaleVotePanel — viewer vote overlay shown during the finale.
 *
 * Renders when a vote_window_open WebSocket event arrives.
 * Shows:
 *   - Finalist names with clickable vote buttons
 *   - Live vote bar chart (updates on every vote_update event)
 *   - Countdown timer
 *   - Closed state with winner reveal after window closes
 */

import { useState, useEffect, useRef } from 'react';
import type {
  VoteWindowOpenEvent,
  VoteUpdateEvent,
  VoteWindowClosedEvent,
} from '@/types/events';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface Finalist {
  agent_id: string;
  display_name: string;
}

interface Props {
  openEvent:    VoteWindowOpenEvent | null;
  updateEvent:  VoteUpdateEvent | null;
  closedEvent:  VoteWindowClosedEvent | null;
}

export default function FinaleVotePanel({ openEvent, updateEvent, closedEvent }: Props) {
  const [counts, setCounts]           = useState<Record<string, number>>({});
  const [totalVotes, setTotalVotes]   = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [voted, setVoted]             = useState<string | null>(null);
  const [closed, setClosed]           = useState(false);
  const [finalists, setFinalists]     = useState<Finalist[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // When vote window opens
  useEffect(() => {
    if (!openEvent) return;
    setFinalists(openEvent.finalists);
    setCounts({});
    setTotalVotes(0);
    setClosed(false);
    setVoted(null);

    const remaining = Math.max(0, openEvent.closes_at_unix - Date.now() / 1000);
    setSecondsLeft(Math.ceil(remaining));

    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      const secs = Math.max(0, openEvent.closes_at_unix - Date.now() / 1000);
      setSecondsLeft(Math.ceil(secs));
      if (secs <= 0 && timerRef.current) clearInterval(timerRef.current);
    }, 500);

    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [openEvent]);

  // Live tally updates
  useEffect(() => {
    if (!updateEvent) return;
    setCounts(updateEvent.counts);
    setTotalVotes(updateEvent.total);
  }, [updateEvent]);

  // Window closed — final results
  useEffect(() => {
    if (!closedEvent) return;
    setCounts(closedEvent.counts);
    setTotalVotes(closedEvent.total);
    setClosed(true);
    setSecondsLeft(0);
    if (timerRef.current) clearInterval(timerRef.current);
  }, [closedEvent]);

  // Don't render until the vote window is opened
  if (!openEvent) return null;

  const castVote = async (finalist: Finalist) => {
    if (voted || closed) return;
    setVoted(finalist.display_name);
    try {
      await fetch(`${API_BASE}/vote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id:  finalist.agent_id,
          viewer_id: `ip:${Math.random().toString(36).slice(2)}`,  // anonymous overlay voter
        }),
      });
    } catch {
      // silently ignore — vote may have landed anyway
    }
  };

  const maxVotes = Math.max(1, ...Object.values(counts));
  const winner   = closed && totalVotes > 0
    ? Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0]
    : null;

  return (
    <div className="absolute inset-0 flex items-center justify-center bg-black/70 z-50 pointer-events-auto">
      <div className="bg-[#0d1b2a] border border-yellow-500/40 rounded-2xl p-6 w-[420px] shadow-2xl">

        {/* Header */}
        <div className="text-center mb-4">
          <p className="text-yellow-400 text-xs uppercase tracking-widest mb-1">
            {closed ? 'VOTES CAST' : 'FINALE — VIEWER VOTE'}
          </p>
          <h2 className="text-white text-2xl font-bold">
            {closed
              ? winner ? `${winner} wins!` : 'No votes cast'
              : 'Who deserves to win?'}
          </h2>
          {!closed && (
            <p className="text-zinc-400 text-sm mt-1">
              ⏱ {secondsLeft}s remaining
            </p>
          )}
        </div>

        {/* Vote buttons + bars */}
        <div className="space-y-4">
          {finalists.map((f) => {
            const voteCount = counts[f.display_name] ?? 0;
            const pct       = totalVotes > 0 ? (voteCount / totalVotes) * 100 : 0;
            const isWinner  = closed && f.display_name === winner;
            const isVoted   = voted === f.display_name;

            return (
              <div key={f.agent_id}>
                <div className="flex justify-between items-center mb-1">
                  <span className={`text-sm font-semibold ${isWinner ? 'text-yellow-400' : 'text-white'}`}>
                    {f.display_name} {isWinner ? '🏆' : ''}
                  </span>
                  <span className="text-xs text-zinc-400">
                    {voteCount} vote{voteCount !== 1 ? 's' : ''} ({pct.toFixed(0)}%)
                  </span>
                </div>

                {/* Vote bar */}
                <div className="h-2 bg-zinc-800 rounded-full overflow-hidden mb-2">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${isWinner ? 'bg-yellow-400' : 'bg-blue-500'}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>

                {/* Vote button */}
                {!closed && (
                  <button
                    onClick={() => castVote(f)}
                    disabled={!!voted}
                    className={`w-full py-2 rounded-lg text-sm font-bold transition-all duration-200
                      ${isVoted
                        ? 'bg-blue-600 text-white cursor-default'
                        : voted
                          ? 'bg-zinc-700 text-zinc-500 cursor-not-allowed'
                          : 'bg-blue-500 hover:bg-blue-400 text-white cursor-pointer'
                      }`}
                  >
                    {isVoted ? `✓ Voted for ${f.display_name}` : `Vote for ${f.display_name}`}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <p className="text-center text-zinc-500 text-xs mt-4">
          {closed
            ? `Final: ${totalVotes} total viewer votes`
            : 'Twitch: type !vote <name> in chat'}
        </p>
      </div>
    </div>
  );
}
