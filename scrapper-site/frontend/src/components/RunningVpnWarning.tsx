import { useEffect, useState } from "react";
import { listRuns, queueStatus, stopRun } from "../api";
import { useNetworkStatus } from "./NetworkStatus";

export default function RunningVpnWarning() {
  const { status } = useNetworkStatus();
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [dismissedRunId, setDismissedRunId] = useState<number | null>(null);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status?.vpn_likely !== false) {
      setActiveRunId(null);
      setDismissedRunId(null);
      return;
    }

    let cancelled = false;
    const checkActiveRun = async () => {
      try {
        const [queue, runs] = await Promise.all([queueStatus(), listRuns()]);
        if (cancelled) return;
        const runId = queue.active_run_ids.find((id) =>
          runs.some((run) => run.id === id && run.status === "running")
        ) ?? null;
        const active = runId !== null;
        setActiveRunId(active ? runId : null);
        if (!active) setDismissedRunId(null);
      } catch {
        // The regular API auth/error handling remains responsible for session issues.
      }
    };

    void checkActiveRun();
    const timer = window.setInterval(() => void checkActiveRun(), 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [status?.vpn_likely]);

  const dismiss = () => {
    setDismissedRunId(activeRunId);
    setError(null);
  };

  const stopActiveRun = async () => {
    if (activeRunId === null) return;
    setStopping(true);
    setError(null);
    try {
      await stopRun(activeRunId);
      setActiveRunId(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setStopping(false);
    }
  };

  if (status?.vpn_likely !== false || activeRunId === null || dismissedRunId === activeRunId) return null;

  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="vpn-warning-dialog" role="alertdialog" aria-modal="true" aria-labelledby="running-vpn-warning-title">
        <h2 id="running-vpn-warning-title">VPN not detected during crawl</h2>
        <p>Run #{activeRunId} is active, but no VPN-like adapter is currently detected on this host.</p>
        <p>You can stop the crawl or let it continue using the current network route.</p>
        {status.public_ip && <p className="muted">Current public IP: {status.public_ip}</p>}
        <small className="muted">Detection is approximate and does not confirm which route the target site receives.</small>
        {error && <p className="error">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="danger" onClick={() => void stopActiveRun()} disabled={stopping}>
            {stopping ? "Stopping…" : "Stop crawl"}
          </button>
          <button type="button" onClick={dismiss}>Continue crawl</button>
        </div>
      </section>
    </div>
  );
}
