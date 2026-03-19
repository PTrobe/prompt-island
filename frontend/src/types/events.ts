export type ActionType =
  | 'speak_public'
  | 'speak_private'
  | 'vote'
  | 'system_event'
  | 'agent_move'
  | 'camera_focus'
  | 'phase_change'
  | 'elimination'
  | 'vote_window_open'
  | 'vote_window_closed'
  | 'vote_update';

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

/** Fired when the backend advances game phase — island scene repositions all agents. */
export interface PhaseChangeEvent {
  type: 'phase_change';
  phase: string;
  day_number: number;
}

/** Fired to move a single agent to a named location on the island. */
export interface AgentMoveEvent {
  type: 'agent_move';
  agent_id: string;
  location: string;
  spot_index?: number;
}

/** Fired to snap / zoom the camera to a named location. */
export interface CameraFocusEvent {
  type: 'camera_focus';
  location: string;
  zoom?: number;
  hold_ms?: number;
}

/** Broadcast when the finale viewer vote window opens. */
export interface VoteWindowOpenEvent {
  action_type: 'vote_window_open';
  day_number: number;
  phase: 'finale';
  finalists: Array<{ agent_id: string; display_name: string }>;
  window_seconds: number;
  closes_at_unix: number;
}

/** Broadcast when a new vote arrives (live tally update). */
export interface VoteUpdateEvent {
  action_type: 'vote_update';
  counts: Record<string, number>;   // display_name → count
  total: number;
}

/** Broadcast when the voting window closes. */
export interface VoteWindowClosedEvent {
  action_type: 'vote_window_closed';
  day_number: number;
  phase: 'finale';
  counts: Record<string, number>;
  total: number;
}
