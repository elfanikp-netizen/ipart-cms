import { useEffect, useState } from "react";
import type { Activity, ActivityPage as ActivityPageData } from "../types";
import { errorText, listActivityPage, listActivityUsers } from "../api";
import { useAuth } from "../auth";
import "./activity.css";

const ACTION_LABEL: Record<string, string> = {
  login: "🔑 login",
  logout: "↩ signed out",
  create_run: "▶ queued run",
  stop_run: "■ stopped run",
  continue_run: "↻ continued run",
  download_output: "↓ downloaded output",
  run_success: "✓ run finished",
  run_failed: "! run failed",
  run_stopped: "■ run stopped",
  show_browser: "▣ showed browser",
  hide_browser: "▣ hid browser",
  update_profile: "✏️ updated profile",
  create_user: "➕ created account",
  update_user: "✏️ updated account",
  delete_user: "🗑 deleted account",
};

export default function ActivityPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "superadmin";

  const [rows, setRows] = useState<Activity[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [search, setSearch] = useState("");
  const [users, setUsers] = useState<Array<{ id: number; username: string }>>([]);
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (isAdmin) listActivityUsers().then(setUsers).catch((e) => setError(errorText(e)));
  }, [isAdmin]);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      listActivityPage({ page, page_size: 25, search, username: isAdmin ? username : "" })
        .then((result: ActivityPageData) => {
          if (!active) return;
          setRows(result.items);
          setTotal(result.total);
          setPages(result.pages);
          setError("");
        })
        .catch((e) => { if (active) setError(errorText(e)); });
    }, 180);
    return () => { active = false; window.clearTimeout(timer); };
  }, [page, search, username, isAdmin]);

  return (
    <section className="card">
      <div className="card-header">
        <h1>Activity history{!isAdmin && <span className="muted"> (your activity)</span>}</h1>
        <div className="toolbar">
          {isAdmin && (
            <select value={username} onChange={(e) => { setUsername(e.target.value); setPage(1); }}>
              <option value="">All users</option>
              {users.map((u) => (
                <option key={u.id} value={u.username}>{u.username}</option>
              ))}
            </select>
          )}
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="scraper-activity-search"><input type="search" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Search activity…" aria-label="Search activity" /></div>
      {rows.length === 0 ? (
        <p className="muted">{username ? "No activity for this user." : "No activity yet."}</p>
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
      <div className="scraper-activity-pagination"><span>{total ? `${(page - 1) * 25 + 1}–${Math.min(page * 25, total)} of ${total}` : "0 results"}</span><button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><span>{page} / {Math.max(1, pages)}</span><button type="button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Next</button></div>
    </section>
  );
}
