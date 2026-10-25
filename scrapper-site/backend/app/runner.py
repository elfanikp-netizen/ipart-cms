"""Serial queue that runs crawler scripts as native subprocesses.

One run at a time, so the persistent Chrome profiles and CDP ports used by
the scripts never collide. Stdout/stderr are streamed into a per-run log file
and scanned for Cloudflare / human-verification markers.
"""

from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
from pathlib import Path

from .config import settings
from .crawlers import get_crawler
from .db import SessionLocal
from .models import Run, utcnow

# Lines that mean the script is parked on a Cloudflare / human check
WAIT_MARKERS = (
    "verify you are human",
    "human verification",
    "verification page detected",
    "security verification",
    "cloudflare",
)
CLEAR_MARKERS = ("cleared; continuing", "cleared;continuing", "verification passed")

# Progress markers emitted by the crawler scripts:
#   carid / keystone / brands:  "[3/50] PN123 ..."
#   ccc:                        "12:34:56 INFO Progress: 3/50"
PROGRESS_PATTERNS = (
    re.compile(r"^\[(\d+)\s*/\s*(\d+)\]"),
    re.compile(r"Progress:\s*(\d+)\s*/\s*(\d+)"),
)


def _parse_progress(line: str) -> tuple[int, int] | None:
    for pattern in PROGRESS_PATTERNS:
        m = pattern.search(line)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


class Runner:
    def __init__(self) -> None:
        self._q: queue.Queue[int] = queue.Queue()
        self._procs: dict[int, subprocess.Popen] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ API
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True, name="runner")
            self._thread.start()
        # Anything left in "running"/"queued" from a previous API process is stale
        with SessionLocal() as db:
            stale = db.query(Run).filter(Run.status.in_(("running", "queued"))).all()
            for run in stale:
                run.status = "failed"
                run.error = "API restarted while this run was active"
                run.finished_at = utcnow()
            if stale:
                db.commit()

    def enqueue(self, run_id: int) -> None:
        self._q.put(run_id)

    def queue_size(self) -> int:
        return self._q.qsize()

    def active_run_id(self) -> int | None:
        with self._lock:
            return next(iter(self._procs), None)

    def stop(self, run_id: int) -> bool:
        """Kill the process tree of an active run (taskkill /T also kills its Chrome)."""
        with self._lock:
            proc = self._procs.get(run_id)
        if proc is None or proc.poll() is not None:
            return False
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
        )
        return True

    # -------------------------------------------------------------- internal
    def _loop(self) -> None:
        while True:
            run_id = self._q.get()
            try:
                self._execute(run_id)
            except Exception as exc:  # noqa: BLE001
                with SessionLocal() as db:
                    run = db.get(Run, run_id)
                    if run and run.status not in ("stopped",):
                        run.status = "failed"
                        run.error = f"runner error: {exc}"[:4000]
                        run.finished_at = utcnow()
                        db.commit()
            finally:
                with self._lock:
                    self._procs.pop(run_id, None)
                self._q.task_done()

    def _set_waiting(self, run_id: int, waiting: bool) -> None:
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if run and run.waiting_for_human != waiting:
                run.waiting_for_human = waiting
                db.commit()

    def _set_progress(self, run_id: int, done: int, total: int) -> None:
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if run and (run.progress_done, run.progress_total) != (done, total):
                run.progress_done = done
                run.progress_total = total
                db.commit()

    def _execute(self, run_id: int) -> None:
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if run is None or run.status == "stopped":
                return
            spec = get_crawler(run.crawler_id)
            if spec is None:
                run.status = "failed"
                run.error = f"unknown crawler '{run.crawler_id}'"
                run.finished_at = utcnow()
                db.commit()
                return
            params = json.loads(run.params or "{}")
            run.status = "running"
            run.started_at = utcnow()
            db.commit()
            input_path = Path(run.input_path)
            output_path = Path(run.output_path)
            log_path = Path(run.log_path)

        args = spec.build_args(params, input_path, output_path)
        cmdline = [str(spec.python), *args]

        with open(log_path, "a", encoding="utf-8", errors="replace") as log:
            log.write(f"$ {spec.python} {' '.join(args)}\n\n")
            log.flush()
            proc = subprocess.Popen(
                cmdline,
                cwd=str(spec.cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            with self._lock:
                self._procs[run_id] = proc
            with SessionLocal() as db:
                run = db.get(Run, run_id)
                run.pid = proc.pid
                db.commit()

            waiting = False
            last_progress: tuple[int, int] | None = None
            assert proc.stdout is not None
            for line in proc.stdout:
                log.write(line)
                log.flush()
                low = line.lower()
                if not waiting and any(m in low for m in WAIT_MARKERS):
                    waiting = True
                    self._set_waiting(run_id, True)
                elif waiting and any(m in low for m in CLEAR_MARKERS):
                    waiting = False
                    self._set_waiting(run_id, False)
                progress = _parse_progress(line)
                if progress and progress != last_progress and progress[1] > 0:
                    last_progress = progress
                    self._set_progress(run_id, progress[0], progress[1])
            returncode = proc.wait()

        with SessionLocal() as db:
            run = db.get(Run, run_id)
            run.returncode = returncode
            run.waiting_for_human = False
            run.finished_at = utcnow()
            if run.status == "stopped":
                pass  # user stopped it; keep status
            elif returncode == 0 and output_path.exists():
                run.status = "success"
                if run.progress_total:
                    run.progress_done = run.progress_total
            elif returncode == 0:
                run.status = "success"
                run.error = "script exited 0 but produced no output file"
                if run.progress_total:
                    run.progress_done = run.progress_total
            else:
                run.status = "failed"
                run.error = f"exit code {returncode} — see log"
            db.commit()


runner = Runner()
