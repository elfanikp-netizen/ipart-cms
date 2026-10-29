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

export interface ActivityPage {
  items: Activity[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface Crawler {
  id: string;
  name: string;
  group: string;
  available: boolean;
  column_required: boolean;
  column_allowed: boolean;
  supports_limit: boolean;
  supports_delay: boolean;
  supports_fresh: boolean;
  supports_show: boolean;
  supports_debug: boolean;
  supports_manual_login: boolean;
  supports_description: boolean;
  description_default: string;
  sites: { key: string; label: string; script: string; supports_fresh?: boolean | null }[];
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
  can_continue: boolean;
  supports_resume: boolean;
  can_manage: boolean;
  supports_live_visibility: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface QueueStatus {
  queued: number;
  active_run_id: number | null;
  active_run_ids: number[];
}

export interface NetworkStatus {
  public_ip: string | null;
  public_ip_check: "complete" | "unavailable";
  vpn_adapters: { Name?: string; InterfaceDescription?: string }[];
  adapter_check: "complete" | "unavailable";
  vpn_likely: boolean | null;
  note: string;
}

export interface RunLog {
  lines: string[];
  truncated: boolean;
}
