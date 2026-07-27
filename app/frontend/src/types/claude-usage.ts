export interface TokenTotals {
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_creation_tokens: number;
  messages: number;
}

export interface ClaudeUsage {
  available: boolean;
  message: string | null;
  live: boolean;
  session_started_at: string | null;
  session_last_activity_at: string | null;
  session_elapsed_seconds: number | null;
  session_project: string | null;
  today: TokenTotals;
  today_sessions: number;
  limit_window_active: boolean;
  limit_window_started_at: string | null;
  limit_window_resets_at: string | null;
  limit_window_remaining_seconds: number | null;
  limit_window: TokenTotals;
}
