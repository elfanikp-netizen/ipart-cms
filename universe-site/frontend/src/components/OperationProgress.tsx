import { dismissOperation, useOperationProgress } from "./operation-progress-store";
import "./operationProgress.css";

const phaseLabels = {
  uploading: "Uploading file",
  processing: "Processing on server",
  downloading: "Downloading file",
  complete: "Complete",
  error: "Failed",
} as const;

export default function OperationProgress() {
  const operation = useOperationProgress();
  if (!operation) return null;

  const determinate = operation.percent !== null
    && (operation.phase === "uploading" || operation.phase === "downloading" || operation.phase === "complete");
  const complete = operation.phase === "complete";
  const failed = operation.phase === "error";
  const detail = failed ? operation.error : complete
    ? operation.kind === "import" ? "Import finished. Review the report below for row details." : "Your file is ready."
    : determinate ? `${operation.percent}%` : "Working…";

  return (
    <section className={`operation-progress${failed ? " failed" : complete ? " complete" : ""}`} aria-live={failed ? "assertive" : "polite"} role={failed ? "alert" : "status"}>
      <span className="operation-progress-mark" aria-hidden="true">{failed ? "!" : complete ? "✓" : "↻"}</span>
      <div className="operation-progress-content">
        <div className="operation-progress-heading">
          <strong>{operation.label} {operation.kind}</strong>
          <span>{phaseLabels[operation.phase]}</span>
        </div>
        {failed ? <p>{detail}</p> : (
          <div className="operation-progress-track" aria-label={`${phaseLabels[operation.phase]}${determinate ? ` ${operation.percent}%` : ""}`}>
            <span
              className={determinate ? "determinate" : "indeterminate"}
              style={determinate ? { width: `${operation.percent}%` } : undefined}
            />
          </div>
        )}
        {!failed && <small>{detail}</small>}
      </div>
      {(complete || failed) && (
        <button type="button" className="operation-progress-dismiss" onClick={() => dismissOperation(operation.id)} aria-label="Dismiss operation status">×</button>
      )}
    </section>
  );
}
