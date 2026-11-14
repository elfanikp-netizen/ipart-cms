import { useSyncExternalStore } from "react";

export type OperationKind = "import" | "export";
export type OperationPhase = "uploading" | "processing" | "downloading" | "complete" | "error";

export interface OperationProgressState {
  id: number;
  kind: OperationKind;
  label: string;
  phase: OperationPhase;
  percent: number | null;
  error?: string;
}

let nextId = 0;
let snapshot: OperationProgressState | null = null;
let clearTimer: number | undefined;
const listeners = new Set<() => void>();

function publish(next: OperationProgressState | null) {
  snapshot = next;
  listeners.forEach((listener) => listener());
}

export function beginOperation(kind: OperationKind, label: string, phase: OperationPhase) {
  const id = ++nextId;
  window.clearTimeout(clearTimer);
  publish({ id, kind, label, phase, percent: phase === "uploading" ? 0 : null });
  return id;
}

export function updateOperation(id: number, patch: Partial<OperationProgressState>) {
  if (snapshot?.id === id) publish({ ...snapshot, ...patch });
}

export function finishOperation(id: number, error?: string) {
  if (snapshot?.id !== id) return;
  if (error) {
    publish({ ...snapshot, phase: "error", error, percent: null });
    return;
  }
  publish({ ...snapshot, phase: "complete", percent: 100 });
  clearTimer = window.setTimeout(() => {
    if (snapshot?.id === id) publish(null);
  }, 8000);
}

export function dismissOperation(id: number) {
  if (snapshot?.id === id && (snapshot.phase === "complete" || snapshot.phase === "error")) publish(null);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return snapshot;
}

export function useOperationProgress() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
