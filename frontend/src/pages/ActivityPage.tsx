import { useEffect, useState } from "react";
import type { Activity, User } from "../types";
import { errorText, listActivity, listUsers } from "../api";
import { useAuth } from "../auth";

const ACTION_LABEL: Record<string, string> = {
  login: "🔑 login",
  create_run: "▶ queued run",
  stop_run: "■ stopped run",
  create_user: "➕ created account",
  update_user: "✏️ updated account",
  delete_user: "🗑 deleted account",
};

export default function ActivityPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "superadmin";

  const [rows, setRows] = useState<Activity[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);

  // debounce the search box so we don't call the API on every keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    if (isAdmin) listUsers().then(setUsers).catch(() => {});
  }, [isAdmin]);

  useEffect(() => {
    const load = () =>
      listActivity(200, debouncedQ, isAdmin ? username : "").then(setRows).catch((e) => setError(errorText(e)));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [debouncedQ, username, isAdmin]);

  return (
    <section className="card">
      <div className="card-header">
        <h1>Activity history{!isAdmin && <span className="muted"> (your activity)</span>}</h1>
        <div className="toolbar">
          <input
            className="search"
            type="search"
            placeholder="Search action or detail…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {isAdmin && (
            <select value={username} onChange={(e) => setUsername(e.target.value)}>
              <option value="">All users</option>
              {users.map((u) => (
                <option key={u.id} value={u.username}>{u.username}</option>
              ))}
            </select>
          )}
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {rows.length === 0 ? (
        <p className="muted">{debouncedQ || username ? "No activity matches the filter." : "No activity yet."}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>User</th>
              <th>Action</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <td>{new Date(a.created_at).toLocaleString()}</td>
                <td>{a.username}</td>
                <td>{ACTION_LABEL[a.action] ?? a.action}</td>
                <td className="muted">{a.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
