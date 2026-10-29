import axios from "axios";
import type { Activity, ActivityPage, Crawler, NetworkStatus, QueueStatus, Run, RunLog, User } from "./types";

// Same-origin by default: the Vite dev proxy (and any reverse proxy like ngrok)
// forwards /api to the backend, so the UI works over the tunnel URL too.
// Override with VITE_API_URL if the API is hosted on a different origin.
const API: string = (import.meta as any).env?.VITE_API_URL ?? "";

export const client = axios.create({ baseURL: API, withCredentials: true });

// AuthContext registers its logout here; called when the token is rejected.
let onUnauthorized: (() => void) | null = null;
export function setOnUnauthorized(cb: (() => void) | null) {
  onUnauthorized = cb;
}

client.interceptors.response.use(
  (res) => res,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      // Token expired/invalid while logged in -> drop session, go to /login.
      if (onUnauthorized) onUnauthorized();
    }
    return Promise.reject(error);
  }
);

export function errorText(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const detail = (e.response?.data as any)?.detail;
    return detail ? `${e.response?.status} ${detail}` : e.message;
  }
  return String(e);
}

// ---------------------------------------------------------------- auth
export const login = (username: string, password: string, remember = false) =>
  client.post<User>("/api/auth/login", { username, password, remember }).then((r) => r.data);

export const fetchMe = () => client.get<User>("/api/auth/me").then((r) => r.data);

// ---------------------------------------------------------------- profile
export const getProfile = () => client.get<User>("/api/profile").then((r) => r.data);
export const updateProfile = (data: {
  display_name?: string;
  current_password?: string;
  new_password?: string;
}) => client.patch<User>("/api/profile", data).then((r) => r.data);

// ---------------------------------------------------------------- users (superadmin)
export const listUsers = () => client.get<User[]>("/api/users").then((r) => r.data);
export const listActivityUsers = () => client.get<Array<Pick<User, "id" | "username">>>("/api/activity/users").then((r) => r.data);
export const createUser = (data: { username: string; password: string; display_name?: string; role?: string }) =>
  client.post<User>("/api/users", data).then((r) => r.data);
export const updateUser = (id: number, data: Partial<{ password: string; display_name: string; role: string; is_active: boolean }>) =>
  client.put<User>(`/api/users/${id}`, data).then((r) => r.data);
export const deleteUser = (id: number) => client.delete(`/api/users/${id}`).then(() => undefined);

// ---------------------------------------------------------------- activity
export const listActivity = (limit = 100, q = "", username = "") => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (q) params.set("q", q);
  if (username) params.set("username", username);
  return client.get<Activity[]>(`/api/activity?${params}`).then((r) => r.data);
};
export const listActivityPage = (params: { page: number; page_size: number; search: string; username: string }) =>
  client.get<ActivityPage>("/api/activity/page", { params }).then((r) => r.data);
export const listUserActivity = (userId: number, limit = 100) =>
  client.get<Activity[]>(`/api/users/${userId}/activity?limit=${limit}`).then((r) => r.data);

// ---------------------------------------------------------------- crawlers & runs
export const listCrawlers = () => client.get<Crawler[]>("/api/crawlers").then((r) => r.data);
export const listRuns = () => client.get<Run[]>("/api/runs").then((r) => r.data);
export const getRun = (id: number) => client.get<Run>(`/api/runs/${id}`).then((r) => r.data);
export const getRunLog = (id: number) => client.get<RunLog>(`/api/runs/${id}/log?tail=400`).then((r) => r.data);
export const queueStatus = () => client.get<QueueStatus>("/api/queue").then((r) => r.data);
export const getNetworkStatus = () => client.get<NetworkStatus>("/api/network-status").then((r) => r.data);
export const stopRun = (id: number) => client.post<Run>(`/api/runs/${id}/stop`).then((r) => r.data);
export const setBrowserVisibility = (id: number, visible: boolean) =>
  client.post<Run>(`/api/runs/${id}/browser-visibility`, new URLSearchParams({ visible: String(visible) })).then((r) => r.data);
export const continueRun = (id: number) => client.post<Run>(`/api/runs/${id}/continue`).then((r) => r.data);

export const outputUrl = (id: number) => `${API}/api/runs/${id}/output`;

export function createRun(crawlerId: string, file: File, opts: Record<string, string | number | boolean>) {
  const form = new FormData();
  form.append("crawler_id", crawlerId);
  form.append("file", file);
  for (const [k, v] of Object.entries(opts)) form.append(k, String(v));
  return client.post<Run>("/api/runs", form).then((r) => r.data);
}
