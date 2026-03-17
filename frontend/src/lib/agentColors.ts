/**
 * Per-agent color assignments for the UI.
 * Each agent has a distinct text color and a subtle background tint for the
 * Confessional bubble. Colors are tuned to be readable on a dark background.
 */

export const AGENT_COLORS: Record<string, string> = {
  agent_01_machiavelli: 'text-amber-400',
  agent_02_chaos:       'text-orange-500',
  agent_03_empath:      'text-emerald-400',
  agent_04_pedant:      'text-blue-400',
  agent_05_paranoid:    'text-red-400',
  agent_06_floater:     'text-slate-300',
  game_master:          'text-purple-400',
};

export const AGENT_BG_COLORS: Record<string, string> = {
  agent_01_machiavelli: 'bg-amber-950/40  border-amber-800/40',
  agent_02_chaos:       'bg-orange-950/40 border-orange-800/40',
  agent_03_empath:      'bg-emerald-950/40 border-emerald-800/40',
  agent_04_pedant:      'bg-blue-950/40   border-blue-800/40',
  agent_05_paranoid:    'bg-red-950/40    border-red-800/40',
  agent_06_floater:     'bg-zinc-900      border-zinc-700',
  game_master:          'bg-purple-950/40 border-purple-800/40',
};

export const AGENT_DOT_COLORS: Record<string, string> = {
  agent_01_machiavelli: 'bg-amber-400',
  agent_02_chaos:       'bg-orange-500',
  agent_03_empath:      'bg-emerald-400',
  agent_04_pedant:      'bg-blue-400',
  agent_05_paranoid:    'bg-red-400',
  agent_06_floater:     'bg-slate-300',
  game_master:          'bg-purple-400',
};
