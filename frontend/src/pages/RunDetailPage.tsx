import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Run, RunLog } from "../types";
import { errorText, getRun, getRunLog, client, stopRun } from "../api";
import ProgressBar from "../components/ProgressBar";

export default function RunDetailPage() {
  const { id } = useParams();
  const runId = Number(id);
  const [run, setRun] = useState<Run | null>(null);
  const [log, setLog] = useState<RunLog>({ lines: [], truncated: false });
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    let timer: number | undefined;
    const load = async () => {
      try {
        const [r, l] = await Promise.all([getRun(runId), getRunLog(runId)]);
        setRun(r);
        setLog(l);
        if (r.status === "queued" || r.status === "running") {
          timer = window.setTimeout(load, 2000);
        }
      } catch (e) {
        setError(errorText(e));
      }
    };
    load();
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [runId]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [log]);

  if (error) return <p className="error">{error}</p>;
  if (!run) return <p>Loading…</p>;

  const active = run.status === "queued" || run.status === "running";
  let params: Record<string, unknown> = {};
  try {
    params = JSON.parse(run.params || "{}");
  } catch {
    /* ignore */
  }

  const downloadOutput = async () => {
    const res = await client.get(`/api/runs/${run.id}/output`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data as Blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${run.crawler_id}_run${run.id}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section>
      <p><Link to="/">← Back to dashboard</Link></p>
      <h1>
        Run #{run.id} — {run.crawler_name}{" "}
        <span className={`status ${run.status}`}>{run.status}</span>
        {run.waiting_for_human && (
          <span className="status waiting">⚠ waiting for human verification</span>
        )}
      </h1>

      {run.waiting_for_human && (
        <div className="alert">
          A Cloudflare / human-verification check is showing. Open the Chrome window on this
          machine, complete the check — the run continues automatically.
        </div>
      )}

      <ProgressBar run={run} />

      <div className="actions-bar">
        {active && (
          <button className="danger" onClick={() => stopRun(run.id).then(setRun)}>
            ■ Stop run
          </button>
        )}
        {run.has_output && (
          <button onClick={downloadOutput}>⬇ Download output Excel</button>
        )}
      </div>

      <dl className="meta">
        <dt>Input file</dt>
        <dd>{String(params.original_filename ?? "-")}</dd>
        {Boolean(params.site) && (<><dt>Site</dt><dd>{String(params.site)}</dd></>)}
        {Boolean(params.column) && (<><dt>Column</dt><dd>{String(params.column)}</dd></>)}
        <dt>Created</dt>
        <dd>{new Date(run.created_at).toLocaleString()}</dd>
        <dt>Started</dt>
        <dd>{run.started_at ? new Date(run.started_at).toLocaleString() : "-"}</dd>
        <dt>Finished</dt>
        <dd>{run.finished_at ? new Date(run.finished_at).toLocaleString() : "-"}</dd>
        {run.returncode !== null && (<><dt>Exit code</dt><dd>{run.returncode}</dd></>)}
      </dl>

      {run.error && <pre className="error-block">{run.error}</pre>}

      <h2>Log {log.truncated && <span className="muted">(last part)</span>}</h2>
      <pre className="log" ref={logRef}>
        {log.lines.length ? log.lines.join("\n") : "No output yet…"}
      </pre>
    </section>
  );
}
