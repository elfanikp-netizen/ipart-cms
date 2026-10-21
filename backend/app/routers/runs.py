import json
import os
import subprocess
import urllib.request
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..crawlers import CRAWLERS, get_crawler
from ..db import SessionLocal
from ..deps import get_current_user, log_activity
from ..models import Run, User
from ..runner import runner
from ..schemas import QueueOut, RunOut

router = APIRouter(prefix="/api", tags=["runs"])

ALLOWED_INPUT_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
LOG_TAIL_BYTES = 256 * 1024
VPN_ADAPTER_PATTERN = r"(?i)(vpn|wireguard|wintun|tap-windows|openvpn|nordlynx|tailscale|zerotier|anyconnect|fortinet|forticlient|globalprotect|proton|mullvad|expressvpn|nordvpn)"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_out(run: Run) -> RunOut:
    spec = get_crawler(run.crawler_id)
    out = RunOut.model_validate(run)
    out.crawler_name = spec.name if spec else run.crawler_id
    out.has_output = bool(run.output_path) and Path(run.output_path).exists()
    out.username = run.user.username if run.user else ""
    return out


@router.get("/crawlers")
def list_crawlers(_: User = Depends(get_current_user)):
    return [spec.to_dict() for spec in CRAWLERS.values()]


@router.get("/queue", response_model=QueueOut)
def queue_status(_: User = Depends(get_current_user)):
    return QueueOut(queued=runner.queue_size(), active_run_id=runner.active_run_id())


@router.get("/network-status")
def network_status(_: User = Depends(get_current_user)):
    """Estimate VPN use on this Windows host; does not prove the target site route."""
    vpn_adapters: list[dict[str, str]] = []
    adapter_check = "unavailable"
    if os.name == "nt":
        script = (
            "Get-NetAdapter -IncludeHidden -ErrorAction Stop | "
            f"Where-Object {{ $_.Status -eq 'Up' -and ($_.Name -match '{VPN_ADAPTER_PATTERN}' "
            f"-or $_.InterfaceDescription -match '{VPN_ADAPTER_PATTERN}') }} | "
            "Select-Object Name,InterfaceDescription | ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            adapter_check = "complete"
            if result.stdout.strip():
                parsed = json.loads(result.stdout)
                vpn_adapters = parsed if isinstance(parsed, list) else [parsed]
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            adapter_check = "unavailable"

    public_ip = None
    ip_check = "unavailable"
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as response:
            public_ip = response.read(64).decode("ascii").strip()
            ip_check = "complete"
    except (OSError, UnicodeDecodeError):
        ip_check = "unavailable"

    return {
        "public_ip": public_ip,
        "public_ip_check": ip_check,
        "vpn_adapters": vpn_adapters,
        "adapter_check": adapter_check,
        "vpn_likely": bool(vpn_adapters) if adapter_check == "complete" else None,
        "note": "This checks the crawler host, not the remote browser. VPN adapters are a heuristic; split tunnels and unrecognized VPN clients may not be detected. The public IP is fetched from api.ipify.org and is not saved.",
    }


@router.post("/runs", response_model=RunOut, status_code=201)
async def create_run(
    crawler_id: str = Form(...),
    file: UploadFile = File(...),
    column: str = Form(""),
    site: str = Form(""),
    description: str = Form(""),
    limit: int = Form(0),
    fresh: bool = Form(False),
    show: bool = Form(False),
    debug: bool = Form(False),
    manual_login: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    spec = get_crawler(crawler_id)
    if spec is None:
        raise HTTPException(404, f"Unknown crawler '{crawler_id}'")
    script = spec.resolve_script(site)
    if not script.exists():
        raise HTTPException(400, f"Script not found: {script}")
    if not spec.python.exists():
        raise HTTPException(400, f"Python env not found: {spec.python}")
    if spec.column_required and not column.strip():
        raise HTTPException(400, "This crawler requires a column value")

    suffix = Path(file.filename or "input.xlsx").suffix.lower()
    if suffix not in ALLOWED_INPUT_SUFFIXES:
        raise HTTPException(400, "Input must be an Excel file (.xlsx / .xlsm / .xls)")

    params = {
        "column": column.strip(),
        "site": site.strip(),
        "description": description.strip(),
        "limit": limit,
        "fresh": fresh,
        "show": show,
        "debug": debug,
        "manual_login": manual_login,
        "original_filename": file.filename,
    }

    run = Run(crawler_id=crawler_id, status="queued", params=json.dumps(params), user_id=user.id)
    db.add(run)
    db.commit()
    db.refresh(run)

    run_dir = settings.data_dir / "runs" / str(run.id)
    run_dir.mkdir(parents=True, exist_ok=True)
    input_path = run_dir / f"input{suffix}"
    input_path.write_bytes(await file.read())

    run.input_path = str(input_path)
    run.output_path = str(run_dir / "output.xlsx")
    run.log_path = str(run_dir / "run.log")
    db.commit()

    runner.enqueue(run.id)
    site_suffix = f" [{site.strip()}]" if site.strip() else ""
    description_suffix = f" description={description.strip()!r}" if description.strip() and spec.supports_description else ""
    log_activity(db, user, "create_run", f"queued {spec.name}{site_suffix}{description_suffix} (run #{run.id})")
    return to_out(run)


@router.get("/runs", response_model=list[RunOut])
def list_runs(limit: int = 50, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    runs = db.scalars(select(Run).order_by(Run.id.desc()).limit(limit)).all()
    return [to_out(r) for r in runs]


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return to_out(run)


@router.get("/runs/{run_id}/log")
def get_run_log(run_id: int, tail: int = 300, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if not run.log_path or not Path(run.log_path).exists():
        return {"lines": [], "truncated": False}
    with open(run.log_path, "rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - LOG_TAIL_BYTES))
        data = fh.read().decode("utf-8", errors="replace")
    lines = data.splitlines()
    truncated = size > LOG_TAIL_BYTES or len(lines) > tail
    return {"lines": lines[-tail:], "truncated": truncated}


@router.post("/runs/{run_id}/stop", response_model=RunOut)
def stop_run(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status == "queued":
        # Not started yet — the runner will skip it when dequeued
        run.status = "stopped"
        db.commit()
        log_activity(db, user, "stop_run", f"stopped run #{run.id} (queued)")
    elif run.status == "running":
        killed = runner.stop(run.id)
        run.status = "stopped"
        db.commit()
        log_activity(db, user, "stop_run", f"stopped run #{run.id}")
        if not killed:
            raise HTTPException(409, "Process already exited")
    return to_out(run)


@router.get("/runs/{run_id}/output")
def download_output(run_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if not run.output_path or not Path(run.output_path).exists():
        raise HTTPException(404, "No output file for this run")
    filename = f"{run.crawler_id}_run{run.id}.xlsx"
    return FileResponse(run.output_path, filename=filename)
