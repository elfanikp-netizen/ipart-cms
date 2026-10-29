import { useEffect, useState } from "react";
import { errorText, listActivityPage, listUsers } from "../api";
import type { Activity, ActivityPage as ActivityPageData, User } from "../api";
import "./activity.css";

const EMPTY: ActivityPageData = { items: [], page: 1, page_size: 25, total: 0, pages: 0 };

export default function ActivityPage({ isAdmin }: { isAdmin: boolean }) {
  const [data, setData] = useState(EMPTY);
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState("");
  const [username, setUsername] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isAdmin) listUsers().then(setUsers).catch((reason) => setError(errorText(reason)));
  }, [isAdmin]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      listActivityPage({ page, page_size: 25, search, username: isAdmin ? username : "" })
        .then((result) => { setData(result); setError(""); })
        .catch((reason) => setError(errorText(reason)));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [page, search, username, isAdmin]);

  return (
    <section className="settings-page portal-activity-page">
      <div className="page-heading settings-heading">
        <div><p className="eyebrow">PORTAL / AUDIT</p><h1>Activity</h1><p className="page-intro">Portal account, profile, and session activity.</p></div>
      </div>
      <div className="activity-toolbar">
        <input type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search portal activity" aria-label="Search portal activity" />
        {isAdmin && <select value={username} onChange={(event) => { setUsername(event.target.value); setPage(1); }} aria-label="Filter by user">
          <option value="">All users</option>
          {users.map((user) => <option key={user.id} value={user.username}>{user.username}</option>)}
        </select>}
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="activity-table-wrap">
        <table><thead><tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr></thead>
          <tbody>{data.items.map((row: Activity) => <tr key={row.id}><td>{new Date(row.created_at).toLocaleString()}</td><td>{row.username}</td><td>{row.action}</td><td>{row.detail}</td></tr>)}
            {!data.items.length && <tr><td colSpan={4} className="empty-table">No portal activity found.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="activity-pagination">
        <span>{data.total ? `${(page - 1) * 25 + 1}–${Math.min(page * 25, data.total)} of ${data.total}` : "0 results"}</span>
        <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button>
        <span>{page} / {Math.max(1, data.pages)}</span>
        <button type="button" disabled={page >= data.pages} onClick={() => setPage((value) => value + 1)}>Next</button>
      </div>
    </section>
  );
}