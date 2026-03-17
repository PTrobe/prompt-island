export type ActionType =
  | 'speak_public'
  | 'speak_private'
  | 'vote'
  | 'system_event';

export interface GameEvent {
  timestamp: string;
  day_number: number;
  phase: string;
  agent_id: string;
  display_name: string;
  action_type: ActionType;
  target_agent_id: string | null;
  message: string;
  inner_thought: string | null;
}

export interface Contestant {
  agent_id: string;
  display_name: string;
  is_eliminated: boolean;
  eliminated_on_day: number | null;
}

export interface GameState {
  current_day: number | null;
  current_phase: string | null;
  contestants: Contestant[];
}

export interface ConfessionalState {
  thought: string | null;
  agentId: string;
  displayName: string;
}
