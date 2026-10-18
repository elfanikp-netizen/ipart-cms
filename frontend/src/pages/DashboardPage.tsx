import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Crawler, QueueStatus, Run } from "../types";
import { createRun, errorText, listCrawlers, listRuns, queueStatus, stopRun } from "../api";
import ProgressBar from "../components/ProgressBar";

export default function DashboardPage() {
  const [crawlers, setCrawlers] = useState<Crawler[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [queue, setQueue] = useState<QueueStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  // form state
  const [crawlerId, setCrawlerId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [column, setColumn] = useState("");
  const [limit, setLimit] = useState(0);
  const [fresh, setFresh] = useState(false);
  const [show, setShow] = useState(false);
  const [debug, setDebug] = useState(false);
  const [manualLogin, setManualLogin] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const selected = useMemo(
    () => crawlers.find((c) => c.id === crawlerId) ?? null,
    [crawlers, crawlerId]
  );

  const groups = useMemo(() => {
    const map = new Map<string, Crawler[]>();
    for (const c of crawlers) {
      if (!map.has(c.group)) map.set(c.group, []);
      map.get(c.group)!.push(c);
    }
    return [...map.entries()];
  }, [crawlers]);

  useEffect(() => {
    listCrawlers()
      .then((cs) => {
        setCrawlers(cs);
        const first = cs.find((c) => c.available);
        if (first) setCrawlerId(first.id);
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  useEffect(() => {
    const load = () => {
      listRuns().then(setRuns).catch(() => {});
      queueStatus().then(setQueue).catch(() => {});
    };
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !crawlerId) return;
    setSubmitting(true);
    setError(null);
    try {
      const run = await createRun(crawlerId, file, {
        column, limit, fresh, show, debug, manual_login: manualLogin,
      });
      navigate(`/runs/${run.id}`);
    } catch (err) {
      setError(errorText(err));
      setSubmitting(false);
    }
  };

  const onStop = async (id: number) => {
    await stopRun(id).catch((e) => setError(errorText(e)));
    listRuns().then(setRuns).catch(() => {});
  };

  return (
    <>
      <section className="card">
        <h1>New Run</h1>
        <form onSubmit={submit} className="form">
          <div className="form-row">
            <label>
              Crawler
              <select value={crawlerId} onChange={(e) => setCrawlerId(e.target.value)}>
                {groups.map(([group, cs]) => (
                  <optgroup key={group} label={group}>
                    {cs.map((c) => (
                      <option key={c.id} value={c.id} disabled={!c.available}>
                        {c.name}{!c.available ? " (not found)" : ""}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
            <label>
              Input Excel file
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx,.xlsm,.xls"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                required
              />
            </label>
          </div>
          <div className="form-row">
            {selected?.column_allowed && (
              <label>
                Column {selected.column_required ? "(required)" : "(optional)"}
                <input
                  value={column}
                  onChange={(e) => setColumn(e.target.value)}
                  placeholder="Header name, letters (A/AA) or number"
                />
              </label>
            )}
            {selected?.supports_limit && (
              <label>
                Limit rows (0 = all)
                <input
                  type="number"
                  min={0}
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value))}
                />
              </label>
            )}
          </div>
          <div className="form-row checkboxes">
            {selected?.supports_fresh && (
              <label className="check">
                <input type="checkbox" checked={fresh} onChange={(e) => setFresh(e.target.checked)} />
                Start over (ignore existing results)
              </label>
            )}
            {selected?.supports_show && (
              <label className="check">
                <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />
                Show browser window
              </label>
            )}
            {selected?.supports_manual_login && (
              <label className="check">
                <input type="checkbox" checked={manualLogin} onChange={(e) => setManualLogin(e.target.checked)} />
                Manual login
              </label>
            )}
            {selected?.supports_debug && (
              <label className="check">
                <input type="checkbox" checked={debug} onChange={(e) => setDebug(e.target.checked)} />
                Debug (save HTML/screenshots)
              </label>
            )}
          </div>
          {selected?.notes && <p className="notes">ℹ️ {selected.notes}</p>}
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={submitting || !file || !selected}>
            {submitting ? "Uploading…" : "▶ Queue run"}
          </button>
        </form>
      </section>

      <section className="card">
        <h1>
          Runs{" "}
          {queue && (queue.queued > 0 || queue.active_run_id) && (
            <span className="queue-info">
              (active: {queue.active_run_id ?? "—"}, queued: {queue.queued})
            </span>
          )}
        </h1>
        {runs.length === 0 ? (
          <p className="muted">No runs yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Crawler</th>
                <th>By</th>
                <th>Status</th>
                <th>Created</th>
                <th>Finished</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td><Link to={`/runs/${r.id}`}>{r.id}</Link></td>
                  <td>{r.crawler_name}</td>
                  <td className="muted">{r.username || "-"}</td>
                  <td>
                    <span className={`status ${r.status}`}>{r.status}</span>
                    {r.waiting_for_human && (
                      <span className="status waiting" title="Solve the check in the Chrome window on this machine">
                        ⚠ human check
                      </span>
                    )}
                    {(r.status === "running" || r.status === "queued") && <ProgressBar run={r} />}
                  </td>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                  <td>{r.finished_at ? new Date(r.finished_at).toLocaleString() : "-"}</td>
                  <td className="actions">
                    {(r.status === "queued" || r.status === "running") && (
                      <button className="danger" onClick={() => onStop(r.id)}>■ Stop</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
