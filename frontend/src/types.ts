export interface User {
  id: number;
  username: string;
  display_name: string;
  role: "superadmin" | "user";
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Activity {
  id: number;
  user_id: number | null;
  username: string;
  action: string;
  detail: string;
  created_at: string;
}

export interface Crawler {
  id: string;
  name: string;
  group: string;
  available: boolean;
  column_required: boolean;
  column_allowed: boolean;
  supports_limit: boolean;
  supports_fresh: boolean;
  supports_show: boolean;
  supports_debug: boolean;
  supports_manual_login: boolean;
  sites: { key: string; label: string; script: string }[];
  notes: string;
}

export interface Run {
  id: number;
  crawler_id: string;
  crawler_name: string;
  username: string;
  status: "queued" | "running" | "success" | "failed" | "stopped";
  params: string;
  pid: number | null;
  waiting_for_human: boolean | null;
  progress_done: number | null;
  progress_total: number | null;
  returncode: number | null;
  error: string | null;
  has_output: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface QueueStatus {
  queued: number;
  active_run_id: number | null;
}

export interface RunLog {
  lines: string[];
  truncated: boolean;
}
