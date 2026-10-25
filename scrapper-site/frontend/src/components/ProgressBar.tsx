import type { Run } from "../types";

function formatDuration(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export default function ProgressBar({ run }: { run: Run }) {
  const done = run.progress_done ?? 0;
  const total = run.progress_total ?? 0;
  const known = total > 0;
  const pct = known ? Math.min(100, Math.round((done / total) * 100)) : 0;

  let eta = "";
  if (run.status === "running" && known && done > 0 && run.started_at) {
    const elapsed = (Date.now() - new Date(run.started_at).getTime()) / 1000;
    const perItem = elapsed / done;
    const remaining = perItem * (total - done);
    eta = `ETA ~${formatDuration(remaining)}`;
  }

  return (
    <div className="progress-wrap" title={known ? `${done} / ${total} items` : "waiting for first item"}>
      <div className={`progress-bar${known ? "" : " indeterminate"}`}>
        <div className="progress-fill" style={{ width: known ? `${pct}%` : undefined }} />
      </div>
      <span className="progress-label">
        {known ? `${done}/${total} (${pct}%)` : run.status === "running" ? "starting…" : "—"}
        {eta && <em>{eta}</em>}
      </span>
    </div>
  );
}
