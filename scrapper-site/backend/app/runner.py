"""Run crawler scripts concurrently, isolating crawlers that share a browser."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
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
        self._procs: dict[int, subprocess.Popen] = {}
        self._pending: set[int] = set()
        self._reserved_ports: set[int] = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ API
    def start(self) -> None:
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
        with self._lock:
            self._pending.add(run_id)
        threading.Thread(
            target=self._run_one,
            args=(run_id,),
            daemon=True,
            name=f"run-{run_id}",
        ).start()

    def cancel_pending(self, run_id: int) -> None:
        with self._lock:
            self._pending.discard(run_id)

    def queue_size(self) -> int:
        with self._lock:
            return len(self._pending)

    def active_run_id(self) -> int | None:
        with self._lock:
            return next(iter(self._procs), None)

    def active_run_ids(self) -> list[int]:
        with self._lock:
            return list(self._procs)

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
    def _run_one(self, run_id: int) -> None:
        cdp_port: int | None = None
        try:
            with SessionLocal() as db:
                run = db.get(Run, run_id)
                if run is None or run.status == "stopped":
                    return
                spec = get_crawler(run.crawler_id)
                if spec is None:
                    raise RuntimeError(f"unknown crawler '{run.crawler_id}'")

            with self._lock:
                self._pending.discard(run_id)
            cdp_port = self._reserve_cdp_port()
            self._execute(run_id, cdp_port)
        except Exception as exc:  # noqa: BLE001
            with SessionLocal() as db:
                run = db.get(Run, run_id)
                if run and run.status != "stopped":
                    run.status = "failed"
                    run.error = f"runner error: {exc}"[:4000]
                    run.finished_at = utcnow()
                    db.commit()
        finally:
            with self._lock:
                if cdp_port is not None:
                    self._reserved_ports.discard(cdp_port)
                self._pending.discard(run_id)
                self._procs.pop(run_id, None)

    def _reserve_cdp_port(self) -> int:
        with self._lock:
            for port in range(20000, 45000):
                if port in self._reserved_ports:
                    continue
                with socket.socket() as probe:
                    try:
                        probe.bind(("127.0.0.1", port))
                    except OSError:
                        continue
                self._reserved_ports.add(port)
                return port
        raise RuntimeError("no free browser debugging port is available")

    def _prepare_run_workspace(
        self, spec, run_id: int, cdp_port: int, params: dict
    ) -> tuple[Path, Path, dict[str, str]]:
        workspace = settings.data_dir / "runs" / str(run_id) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        source_script = spec.resolve_script(params.get("site"))
        source_files = {path.name: path for path in spec.cwd.glob("*.py") if path.is_file()}
        source_files[source_script.name] = source_script
        source_text = {name: path.read_text(encoding="utf-8") for name, path in source_files.items()}
        project_ports = {
            int(port)
            for source in source_text.values()
            for port in re.findall(r"(?:CDP_PORT\s*=|\bcdp_port\s*=)\s*(\d+)", source)
        }
        for name, source in source_text.items():
            for port in project_ports:
                source = re.sub(rf"(?<!\d){port}(?!\d)", str(cdp_port), source)
            (workspace / name).write_text(source, encoding="utf-8")
        script_path = workspace / source_script.name

        for name in (".env", "auth_state.json"):
            source_file = spec.cwd / name
            if source_file.is_file():
                shutil.copy2(source_file, workspace / name)
        for source_dir in spec.cwd.iterdir():
            if source_dir.is_dir() and (
                "profile" in source_dir.name.casefold() or source_dir.name == "playwright"
            ):
                destination = workspace / source_dir.name
                if not destination.exists():
                    shutil.copytree(
                        source_dir,
                        destination,
                        ignore=shutil.ignore_patterns(
                            "Singleton*", "DevToolsActivePort", "lockfile", "LOCK"
                        ),
                    )

        import_paths = [str(spec.cwd)]
        shared_dir = spec.cwd.parent / "scrapper-shared"
        if shared_dir.is_dir():
            import_paths.append(str(shared_dir))
        existing_pythonpath = os.environ.get("PYTHONPATH")
        if existing_pythonpath:
            import_paths.append(existing_pythonpath)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(import_paths)
        return script_path, workspace, env

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

    def _execute(self, run_id: int, cdp_port: int) -> None:
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
            workspace_id = run.id

        script_path, workspace, env = self._prepare_run_workspace(
            spec, workspace_id, cdp_port, params
        )
        args = spec.build_args(params, input_path, output_path)
        args[0] = str(script_path)
        cmdline = [str(spec.python), *args]

        with open(log_path, "a", encoding="utf-8", errors="replace") as log:
            log.write(f"$ {spec.python} {' '.join(args)}\n\n")
            log.flush()
            proc = subprocess.Popen(
                cmdline,
                cwd=str(workspace),
                env=env,
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
