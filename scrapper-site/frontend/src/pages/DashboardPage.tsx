import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Crawler, QueueStatus, Run } from "../types";
import { continueRun, createRun, errorText, listCrawlers, listRuns, queueStatus, stopRun } from "../api";
import ProgressBar from "../components/ProgressBar";
import CrawlerSelect from "../components/CrawlerSelect";
import TableSearchPagination, { useTableSearch } from "../components/TableSearchPagination";
import { useNetworkStatus } from "../components/NetworkStatus";

export default function DashboardPage() {
  const [crawlers, setCrawlers] = useState<Crawler[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [queue, setQueue] = useState<QueueStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  // form state
  const [crawlerId, setCrawlerId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [column, setColumn] = useState("");
  const [site, setSite] = useState("");
  const [description, setDescription] = useState("");
  const [limit, setLimit] = useState(0);
  const [fresh, setFresh] = useState(false);
  const [show, setShow] = useState(false);
  const [debug, setDebug] = useState(false);
  const [manualLogin, setManualLogin] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [continuingRunId, setContinuingRunId] = useState<number | null>(null);
  const [showVpnWarning, setShowVpnWarning] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { status: networkStatus, refresh: refreshNetworkStatus } = useNetworkStatus();

  const selected = useMemo(
    () => crawlers.find((c) => c.id === crawlerId) ?? null,
    [crawlers, crawlerId]
  );
  const runsTable = useTableSearch(runs, (run) => [
    run.id,
    run.crawler_name,
    run.username,
    run.status,
    run.created_at,
    run.finished_at,
    run.progress_done,
    run.progress_total,
  ].join(" "));

  // reset the site to the first variant whenever the crawler changes
  useEffect(() => {
    setSite(selected?.sites?.[0]?.key ?? "");
    setDescription(selected?.description_default ?? "");
  }, [selected]);

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

  const queueRun = async () => {
    if (!file || !crawlerId) return;
    setSubmitting(true);
    setError(null);
    setShowVpnWarning(false);
    try {
      const run = await createRun(crawlerId, file, {
        column, site, description, limit, fresh, show, debug, manual_login: manualLogin,
      });
      navigate(`/runs/${run.id}`);
    } catch (err) {
      setError(errorText(err));
      setSubmitting(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !crawlerId) return;
    setError(null);
    const latestStatus = await refreshNetworkStatus();
    if (latestStatus?.vpn_likely !== true) {
      setShowVpnWarning(true);
      return;
    }
    await queueRun();
  };

  const onStop = async (id: number) => {
    await stopRun(id).catch((e) => setError(errorText(e)));
    listRuns().then(setRuns).catch(() => {});
  };

  const onContinue = async (id: number) => {
    setContinuingRunId(id);
    setError(null);
    try {
      const continued = await continueRun(id);
      navigate(`/runs/${continued.id}`);
    } catch (e) {
      setError(errorText(e));
      setContinuingRunId(null);
    }
  };

  const checkNetwork = async () => {
    setCheckingNetwork(true);
    setNetworkError(null);
    try {
      setNetworkStatus(await getNetworkStatus());
    } catch (e) {
      setNetworkError(errorText(e));
    } finally {
      setCheckingNetwork(false);
    }
  };

  return (
    <>
      <section className="card">
        <h1>New Run</h1>
        <form onSubmit={submit} className="form">
          <div className="form-row">
            <CrawlerSelect crawlers={crawlers} value={crawlerId} onChange={setCrawlerId} />
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
            {selected && selected.sites.length > 0 && (
              <label>
                Site
                <select
                  value={site}
                  onChange={(e) => setSite(e.target.value)}
                  disabled={selected.sites.length === 1}
                  title={selected.sites.length === 1 ? "This crawler has a single site" : undefined}
                >
                  {selected.sites.map((s) => (
                    <option key={s.key} value={s.key}>{s.label}</option>
                  ))}
                </select>
              </label>
            )}
            {selected?.supports_description && (
              <label>
                Description match
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. A/M: CAPA"
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

      {showVpnWarning && (
        <div className="dialog-backdrop" role="presentation">
          <section className="vpn-warning-dialog" role="alertdialog" aria-modal="true" aria-labelledby="vpn-warning-title">
            <h2 id="vpn-warning-title">VPN not detected</h2>
            <p>
              {networkStatus?.vpn_likely === false
                ? "No VPN-like active adapter was detected on this host."
                : "The host VPN status could not be confirmed."}
            </p>
            <p>
              The run will use the current network route for {selected?.name ?? "the selected crawler"}
              {site ? ` (${selected?.sites.find((s) => s.key === site)?.label ?? site})` : ""}.
              You can cancel, connect your VPN, and check again, or continue without VPN.
            </p>
            {networkStatus?.public_ip && <p className="muted">Current public IP: {networkStatus.public_ip}</p>}
            <small className="muted">VPN detection is approximate and does not confirm which route the target site receives.</small>
            <div className="dialog-actions">
              <button type="button" className="secondary" onClick={() => setShowVpnWarning(false)}>Cancel</button>
              <button type="button" onClick={() => void queueRun()} disabled={submitting}>
                {submitting ? "Queueing…" : "Continue without VPN"}
              </button>
            </div>
          </section>
        </div>
      )}

      <section className="card">
        <h1>
          Runs{" "}
          {queue && (queue.queued > 0 || queue.active_run_id) && (
            <span className="queue-info">
              (active: {queue.active_run_id ?? "—"}, queued: {queue.queued})
            </span>
          )}
        </h1>
        <TableSearchPagination
          query={runsTable.query}
          onQueryChange={runsTable.setQuery}
          page={runsTable.page}
          pageCount={runsTable.pageCount}
          filteredCount={runsTable.filteredCount}
          start={runsTable.start}
          end={runsTable.end}
          onPageChange={runsTable.setPage}
          placeholder="Search runs…"
        />
        {runs.length === 0 ? (
          <p className="muted">No runs yet.</p>
        ) : runsTable.filteredCount === 0 ? (
          <p className="muted">No runs match your search.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Crawler</th>
                <th>By</th>
                <th>Status</th>
                <th>Runtime</th>
                <th>Created</th>
                <th>Finished</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runsTable.pageRows.map((r) => (
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
                  <td>{formatRuntime(r)}</td>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                  <td>{r.finished_at ? new Date(r.finished_at).toLocaleString() : "-"}</td>
                  <td className="actions">
                    {(r.status === "queued" || r.status === "running") && (
                      <button className="danger" onClick={() => onStop(r.id)}>■ Stop</button>
                    )}
                    {r.status === "stopped" && (
                      <button
                        className="small"
                        onClick={() => void onContinue(r.id)}
                        disabled={!r.can_continue || continuingRunId !== null}
                        title={!r.can_continue ? "Original input workbook or crawler environment is unavailable" : r.supports_resume ? "Continue this run from saved output" : "Continue this run from the next unfinished input row"}
                      >
                        {continuingRunId === r.id ? "Continuing…" : "↻ Continue"}
                      </button>
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

function formatRuntime(run: Run): string {
  if (!run.started_at) return "-";
  const start = new Date(run.started_at).getTime();
  const end = run.finished_at ? new Date(run.finished_at).getTime() : Date.now();
  const totalSeconds = Math.max(0, Math.floor((end - start) / 1000));
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (days) return `${days}d ${hours}h`;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}
