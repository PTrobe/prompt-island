/**
 * HubChat — main panel (70% width) displaying the public event stream.
 *
 * Per FRONTEND_AND_STREAM.md §3:
 *   - Renders speak_public, speak_private, vote, and system_event rows.
 *   - Auto-scrolls to the bottom as new messages arrive.
 *   - Each agent's name appears in their assigned colour.
 *   - Private messages and votes are visually distinct from public speech.
 */

'use client';

import { useEffect, useRef } from 'react';
import { GameEvent } from '@/types/events';
import { AGENT_COLORS, AGENT_DOT_COLORS } from '@/lib/agentColors';

interface Props {
  events: GameEvent[];
}

export default function HubChat({ events }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom whenever a new event is displayed
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 border-b border-zinc-800 text-xs text-zinc-500 uppercase tracking-widest shrink-0">
        The Hub — Public Chat
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2 scrollbar-thin scrollbar-thumb-zinc-700">
        {events.length === 0 && (
          <div className="text-zinc-700 text-sm text-center mt-12">
            Waiting for the game to begin…
          </div>
        )}

        {events.map((event, i) => (
          <ChatRow key={`${event.timestamp}-${i}`} event={event} />
        ))}

        {/* Sentinel for auto-scroll */}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function ChatRow({ event }: { event: GameEvent }) {
  switch (event.action_type) {
    case 'system_event':
      return <SystemEventRow event={event} />;
    case 'vote':
      return <VoteRow event={event} />;
    case 'speak_private':
      return <PrivateRow event={event} />;
    case 'speak_public':
    default:
      return <PublicRow event={event} />;
  }
}

// ---------------------------------------------------------------------------
// Row variants
// ---------------------------------------------------------------------------

function PublicRow({ event }: { event: GameEvent }) {
  const nameColor = AGENT_COLORS[event.agent_id] ?? 'text-zinc-300';
  const dot       = AGENT_DOT_COLORS[event.agent_id] ?? 'bg-zinc-500';

  return (
    <div className="flex items-start gap-3 animate-fade-in">
      {/* Agent dot */}
      <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${dot}`} />

      <div>
        <span className={`font-bold text-sm ${nameColor}`}>{event.display_name}</span>
        <span className="text-zinc-600 text-xs ml-2">{formatPhase(event.phase)}</span>
        <p className="text-zinc-200 text-sm mt-0.5 leading-relaxed">{event.message}</p>
      </div>
    </div>
  );
}

function PrivateRow({ event }: { event: GameEvent }) {
  const nameColor = AGENT_COLORS[event.agent_id] ?? 'text-zinc-300';

  return (
    <div className="flex items-start gap-3 animate-fade-in opacity-70">
      <span className="mt-1.5 text-zinc-600 text-xs shrink-0">🔒</span>
      <div>
        <span className={`font-bold text-sm ${nameColor}`}>{event.display_name}</span>
        {event.target_agent_id && (
          <span className="text-zinc-500 text-xs ml-1">→ {event.target_agent_id}</span>
        )}
        <span className="text-zinc-500 text-xs ml-2">DM</span>
        <p className="text-zinc-400 text-sm mt-0.5 italic leading-relaxed">{event.message}</p>
      </div>
    </div>
  );
}

function VoteRow({ event }: { event: GameEvent }) {
  const nameColor = AGENT_COLORS[event.agent_id] ?? 'text-zinc-300';

  return (
    <div className="flex items-start gap-3 animate-fade-in my-1">
      <span className="mt-1 text-sm shrink-0">🗳️</span>
      <div className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 w-full">
        <div className="text-xs text-zinc-500 mb-1 uppercase tracking-wide">Vote</div>
        <span className={`font-bold text-sm ${nameColor}`}>{event.display_name}</span>
        <span className="text-zinc-400 text-sm"> votes to eliminate </span>
        <span className="text-red-400 font-bold text-sm">{event.target_agent_id ?? '?'}</span>
        {event.message && (
          <p className="text-zinc-400 text-xs mt-1 italic">{event.message}</p>
        )}
      </div>
    </div>
  );
}

function SystemEventRow({ event }: { event: GameEvent }) {
  return (
    <div className="animate-fade-in my-2">
      <div className="bg-purple-950/30 border border-purple-800/40 rounded px-4 py-3 text-center">
        <span className="text-purple-300 text-xs font-bold uppercase tracking-widest block mb-1">
          Game Master
        </span>
        <p className="text-purple-200 text-sm">{event.message}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatPhase(phase: string): string {
  const labels: Record<string, string> = {
    morning_chat:        'Morning Chat',
    challenge:           'Challenge',
    scramble:            'Scramble',
    tribal_council:      'Tribal Council',
    night_consolidation: 'Night',
  };
  return labels[phase] ?? phase;
}
