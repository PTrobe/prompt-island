/**
 * Confessional — left sidebar (30% width) showing an agent's inner thought.
 *
 * Per FRONTEND_AND_STREAM.md §3: visually distinct from the public chat —
 * italicised text on a slightly lighter dark background. Only visible while
 * an agent is currently "thinking" (thought != null).
 */

import { ConfessionalState } from '@/types/events';
import { AGENT_COLORS, AGENT_BG_COLORS } from '@/lib/agentColors';

interface Props {
  state: ConfessionalState;
}

export default function Confessional({ state }: Props) {
  const { thought, agentId, displayName } = state;

  return (
    <div className="w-[30%] shrink-0 flex flex-col bg-zinc-950 border-r border-zinc-800 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 border-b border-zinc-800 text-xs text-zinc-500 uppercase tracking-widest">
        Confessional
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col items-center justify-center p-6">
        {thought ? (
          <div className="animate-fade-in w-full">
            {/* Agent name */}
            <div className={`text-xs font-bold uppercase tracking-widest mb-3 ${AGENT_COLORS[agentId] ?? 'text-zinc-400'}`}>
              {displayName}&apos;s inner thought
            </div>

            {/* Thought bubble */}
            <div
              className={`rounded-lg p-4 border ${AGENT_BG_COLORS[agentId] ?? 'bg-zinc-900 border-zinc-700'}`}
            >
              <p className="italic text-zinc-200 leading-relaxed text-sm">
                &ldquo;{thought}&rdquo;
              </p>
            </div>

            {/* Thinking indicator */}
            <div className="mt-4 flex items-center gap-2 text-xs text-zinc-600">
              <span className="inline-flex gap-1">
                <span className="w-1 h-1 rounded-full bg-zinc-600 animate-bounce [animation-delay:0ms]" />
                <span className="w-1 h-1 rounded-full bg-zinc-600 animate-bounce [animation-delay:150ms]" />
                <span className="w-1 h-1 rounded-full bg-zinc-600 animate-bounce [animation-delay:300ms]" />
              </span>
              <span>processing next move</span>
            </div>
          </div>
        ) : (
          <div className="text-center text-zinc-700 text-sm">
            <div className="text-3xl mb-3">💭</div>
            <div>Waiting for confessional…</div>
          </div>
        )}
      </div>
    </div>
  );
}
