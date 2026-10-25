import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Run, RunLog } from "../types";
import { continueRun, errorText, getRun, getRunLog, client, stopRun } from "../api";
import ProgressBar from "../components/ProgressBar";

export default function RunDetailPage() {
  const { id } = useParams();
  const runId = Number(id);
  const [run, setRun] = useState<Run | null>(null);
  const [log, setLog] = useState<RunLog>({ lines: [], truncated: false });
  const [error, setError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [continueError, setContinueError] = useState<string | null>(null);
  const [continuing, setContinuing] = useState(false);
  const [pollVersion, setPollVersion] = useState(0);
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
  }, [runId, pollVersion]);

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
    setDownloadError(null);
    try {
      const res = await client.get(`/api/runs/${run.id}/output`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data as Blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${run.crawler_id}_run${run.id}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setDownloadError(errorText(e));
    }
  };

  const resumeRun = async () => {
    setContinuing(true);
    setContinueError(null);
    try {
      const updatedRun = await continueRun(run.id);
      setRun(updatedRun);
      setPollVersion((version) => version + 1);
    } catch (e) {
      setContinueError(errorText(e));
    } finally {
      setContinuing(false);
    }
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
        {run.status === "stopped" && (
          <button
            onClick={() => void resumeRun()}
            disabled={!run.can_continue || continuing}
            title={!run.can_continue ? "Input workbook or crawler environment is unavailable" : run.supports_resume ? "Continue this run from saved output" : "Continue this run from the next unfinished input row"}
          >
            {continuing ? "Continuing…" : "↻ Continue run"}
          </button>
        )}
        {run.has_output && (
          <button onClick={() => void downloadOutput()}>⬇ Download output Excel</button>
        )}
      </div>
      {downloadError && <p className="error" role="alert">Download failed: {downloadError}</p>}
      {continueError && <p className="error" role="alert">Continue failed: {continueError}</p>}

      <dl className="meta">
        <dt>Input file</dt>
        <dd>{String(params.original_filename ?? "-")}</dd>
        {Boolean(params.site) && (<><dt>Site</dt><dd>{String(params.site)}</dd></>)}
        {Boolean(params.column) && (<><dt>Column</dt><dd>{String(params.column)}</dd></>)}
        {Boolean(params.description) && (<><dt>Description match</dt><dd>{String(params.description)}</dd></>)}
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
        {log.lines.length
          ? log.lines.join("\n")
          : active
            ? "No output yet. The run log will appear here as the worker starts."
            : "No log file is available for this run."}
      </pre>
    </section>
  );
}
