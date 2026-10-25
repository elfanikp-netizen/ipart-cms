import { useEffect, useState } from "react";
import type { Activity, User } from "../types";
import { errorText, listActivity, listUsers } from "../api";
import { useAuth } from "../auth";
import TableSearchPagination, { useTableSearch } from "../components/TableSearchPagination";

const ACTION_LABEL: Record<string, string> = {
  login: "🔑 login",
  logout: "↩ signed out",
  create_run: "▶ queued run",
  stop_run: "■ stopped run",
  continue_run: "↻ continued run",
  update_profile: "✏️ updated profile",
  create_user: "➕ created account",
  update_user: "✏️ updated account",
  delete_user: "🗑 deleted account",
};

export default function ActivityPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "superadmin";

  const [rows, setRows] = useState<Activity[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const activityTable = useTableSearch(rows, (activity) => [
    activity.username,
    activity.action,
    ACTION_LABEL[activity.action],
    activity.detail,
    activity.created_at,
    new Date(activity.created_at).toLocaleString(),
  ].join(" "));

  useEffect(() => {
    if (isAdmin) listUsers().then(setUsers).catch(() => {});
  }, [isAdmin]);

  useEffect(() => {
    const load = () =>
      listActivity(200, "", isAdmin ? username : "").then(setRows).catch((e) => setError(errorText(e)));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [username, isAdmin]);

  return (
    <section className="card">
      <div className="card-header">
        <h1>Activity history{!isAdmin && <span className="muted"> (your activity)</span>}</h1>
        <div className="toolbar">
          {isAdmin && (
            <select value={username} onChange={(e) => { setUsername(e.target.value); activityTable.resetPage(); }}>
              <option value="">All users</option>
              {users.map((u) => (
                <option key={u.id} value={u.username}>{u.username}</option>
              ))}
            </select>
          )}
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <TableSearchPagination
        query={activityTable.query}
        onQueryChange={activityTable.setQuery}
        page={activityTable.page}
        pageCount={activityTable.pageCount}
        filteredCount={activityTable.filteredCount}
        start={activityTable.start}
        end={activityTable.end}
        onPageChange={activityTable.setPage}
        placeholder="Search activity…"
      />
      {rows.length === 0 ? (
        <p className="muted">{username ? "No activity for this user." : "No activity yet."}</p>
      ) : activityTable.filteredCount === 0 ? (
        <p className="muted">No activity matches your search.</p>
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
            {activityTable.pageRows.map((a) => (
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
