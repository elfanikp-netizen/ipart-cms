import axios from "axios";

export interface User {
  id: number;
  username: string;
  display_name: string;
  role: "superadmin" | "user";
  is_active: boolean;
  app_access: { scraper: boolean; universe: boolean };
  created_at: string;
  last_login_at: string | null;
}

export const client = axios.create({ withCredentials: true });

export function errorText(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
    return detail ?? error.message;
  }
  return String(error);
}

export const login = (username: string, password: string, remember: boolean) =>
  client.post<User>("/api/auth/login", { username, password, remember }).then((response) => response.data);
export const fetchMe = () => client.get<User>("/api/auth/me").then((response) => response.data);
export const logout = () => client.post("/api/auth/logout");
export const updateProfile = (data: { display_name?: string; current_password?: string; new_password?: string }) =>
  client.patch<User>("/api/profile", data).then((response) => response.data);
export const listUsers = () => client.get<User[]>("/api/users").then((response) => response.data);
export const createUser = (data: { username: string; password: string; display_name: string; role: string; app_access: User["app_access"] }) =>
  client.post<User>("/api/users", data).then((response) => response.data);
export const updateUser = (id: number, data: Partial<Pick<User, "display_name" | "role" | "is_active" | "app_access">> & { password?: string }) =>
  client.put<User>(`/api/users/${id}`, data).then((response) => response.data);
export const deleteUser = (id: number) => client.delete(`/api/users/${id}`);