import { useEffect, useState } from "react";
import { errorText, getUniverseActivity } from "../api";
import type { ActivityPage as ActivityPageData } from "../api";
import "./activity.css";

const EMPTY: ActivityPageData = { items: [], page: 1, page_size: 25, total: 0, pages: 0 };

export default function ActivityPage({ isAdmin }: { isAdmin: boolean }) {
  const [data, setData] = useState(EMPTY);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      getUniverseActivity({ page, page_size: 25, search })
        .then((result) => { setData(result); setError(""); })
        .catch((reason) => setError(errorText(reason)));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [page, search]);

  return (
    <section className="content-wrap">
      <div className="page-heading"><div><p className="eyebrow">UNIVERSE / AUDIT</p><h1>Activity</h1><p>{isAdmin ? "Universe data changes and exports across all users." : "Your Universe data changes and exports."}</p></div><div className="heading-count"><strong>{data.total.toLocaleString()}</strong><span>events</span></div></div>
      <div className="universe-activity-toolbar">
        <input type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search Universe activity" aria-label="Search Universe activity" />
      </div>
      {error && <div className="alert error-alert" role="alert">{error}</div>}
      <div className="table-frame">
        <table><thead><tr><th>WHEN</th><th>USER</th><th>ACTION</th><th>DETAIL</th></tr></thead>
          <tbody>{data.items.map((row) => <tr key={row.id}><td>{new Date(row.created_at).toLocaleString()}</td><td>{row.username}</td><td>{row.action}</td><td>{row.detail}</td></tr>)}
            {!data.items.length && <tr><td className="empty-state" colSpan={4}>No Universe activity found.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="table-footer"><span>{data.total ? `${(page - 1) * 25 + 1}–${Math.min(page * 25, data.total)} of ${data.total}` : "0 results"}</span><div><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page} of {Math.max(1, data.pages)}</span><button disabled={page >= data.pages} onClick={() => setPage((value) => value + 1)}>Next →</button></div></div>
    </section>
  );
}