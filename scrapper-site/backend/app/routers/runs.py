import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from zipfile import is_zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..crawlers import CRAWLERS, get_crawler
from ..db import SessionLocal
from ..deps import get_current_user, log_activity
from ..models import Activity, Run, User, utcnow
from ..runner import runner
from ..schemas import ActivityPageOut, QueueOut, RunOut

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


def run_artifact_path(run: Run, name: str) -> Path | None:
    stored_path = getattr(run, f"{name}_path")
    if stored_path:
        path = Path(stored_path)
        if path.is_file():
            return path

    run_dir = settings.data_dir / "runs" / str(run.id)
    filename = {"log": "run.log", "output": "output.xlsx"}.get(name)
    if filename:
        current_path = run_dir / filename
        return current_path if current_path.is_file() else None
    if name == "input":
        return next((path for path in run_dir.glob("input.*") if path.is_file()), None)
    return None


def to_out(run: Run, user: User | None = None) -> RunOut:
    spec = get_crawler(run.crawler_id)
    params = json.loads(run.params or "{}")
    resumable_status = run.status in {"stopped", "failed"}
    out = RunOut.model_validate(run)
    out.crawler_name = spec.name if spec else run.crawler_id
    out.has_output = run_artifact_path(run, "output") is not None
    out.can_continue = (
        resumable_status
        and bool(spec and spec.supports_resume)
        and run_artifact_path(run, "input") is not None
        and spec is not None
        and spec.resolve_script(params.get("site")).is_file()
        and spec.python.is_file()
    )
    out.supports_resume = bool(spec and spec.supports_resume)
    out.can_manage = bool(user and (user.role == "superadmin" or run.user_id == user.id))
    out.supports_live_visibility = bool(
        spec
        and spec.supports_live_visibility
        and (not spec.supports_show or params.get("show") or spec.live_visibility_flag)
    )
    out.browser_visible = runner.browser_is_visible(run.id)
    out.username = run.user.username if run.user else ""
    return out


def require_run_owner_or_admin(run: Run, user: User) -> None:
    if user.role != "superadmin" and run.user_id != user.id:
        raise HTTPException(403, "Only the run owner or a superadmin can perform this action")


@router.get("/crawlers")
def list_crawlers(_: User = Depends(get_current_user)):
    return [spec.to_dict() for spec in CRAWLERS.values()]


@router.get("/queue", response_model=QueueOut)
def queue_status(_: User = Depends(get_current_user)):
    return QueueOut(
        queued=runner.queue_size(),
        active_run_id=runner.active_run_id(),
        active_run_ids=runner.active_run_ids(),
    )


@router.get("/activity")
def list_activity(
    limit: int = 200,
    q: str = "",
    username: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Activity).outerjoin(User, Activity.user_id == User.id).order_by(Activity.id.desc())
    if user.role != "superadmin":
        stmt = stmt.where(Activity.user_id == user.id)
    elif username.strip():
        stmt = stmt.where(User.username == username.strip())
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Activity.action.ilike(like), Activity.detail.ilike(like), User.username.ilike(like)))
    rows = db.scalars(stmt.limit(max(1, min(limit, 1000)))).all()
    return [{
        "id": row.id,
        "user_id": row.user_id,
        "username": row.user.username if row.user else "?",
        "action": row.action,
        "detail": row.detail or "",
        "created_at": row.created_at,
    } for row in rows]


@router.get("/activity/users")
def activity_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "superadmin":
        raise HTTPException(403, "Superadmin only")
    rows = db.execute(
        select(User.id, User.username)
        .join(Activity, Activity.user_id == User.id)
        .distinct()
        .order_by(User.username)
    ).mappings().all()
    return [dict(row) for row in rows]


@router.get("/activity/page", response_model=ActivityPageOut)
def activity_page(
    page: int = 1,
    page_size: int = 25,
    search: str = "",
    username: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    stmt = select(Activity).outerjoin(User, Activity.user_id == User.id)
    if user.role != "superadmin":
        stmt = stmt.where(Activity.user_id == user.id)
    elif username.strip():
        stmt = stmt.where(User.username == username.strip())
    if search.strip():
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Activity.action.ilike(like), Activity.detail.ilike(like), User.username.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.order_by(Activity.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [{
            "id": row.id,
            "user_id": row.user_id,
            "username": row.user.username if row.user else "?",
            "action": row.action,
            "detail": row.detail or "",
            "created_at": row.created_at,
        } for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


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
    delay: float = Form(1.5),
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
        "delay": delay,
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
    return to_out(run, user)


@router.get("/runs", response_model=list[RunOut])
def list_runs(limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    runs = db.scalars(select(Run).order_by(Run.id.desc()).limit(limit)).all()
    return [to_out(r, user) for r in runs]


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return to_out(run, user)


@router.get("/runs/{run_id}/log")
def get_run_log(run_id: int, tail: int = 300, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    log_path = run_artifact_path(run, "log")
    if log_path is None:
        return {"lines": [], "truncated": False}
    with open(log_path, "rb") as fh:
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
    require_run_owner_or_admin(run, user)
    if run.status == "queued":
        runner.cancel_pending(run.id)
        run.status = "stopped"
        run.finished_at = utcnow()
        db.commit()
        log_activity(db, user, "stop_run", f"stopped run #{run.id} (queued)")
    elif run.status == "running":
        killed = runner.stop(run.id, run.pid)
        if not killed:
            raise HTTPException(409, "Crawler process could not be stopped; try again")
        run.status = "stopped"
        run.finished_at = utcnow()
        db.commit()
        log_activity(db, user, "stop_run", f"stopped run #{run.id}")
    return to_out(run, user)


@router.post("/runs/{run_id}/browser-visibility", response_model=RunOut)
def set_browser_visibility(
    run_id: int,
    visible: bool = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    require_run_owner_or_admin(run, user)
    spec = get_crawler(run.crawler_id)
    if spec is None or not spec.supports_live_visibility:
        raise HTTPException(409, "This crawler does not support live browser visibility control")
    if run.status != "running":
        raise HTTPException(409, "Browser visibility can only be changed during an active run")
    if not runner.set_browser_visibility(run_id, visible):
        raise HTTPException(409, "The crawler browser window is not available")
    log_activity(db, user, "show_browser" if visible else "hide_browser", f"run #{run.id}")
    return to_out(run, user)


@router.post("/runs/{run_id}/continue", response_model=RunOut)
def continue_run(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    require_run_owner_or_admin(run, user)
    if run.status not in {"stopped", "failed"}:
        raise HTTPException(409, "Only stopped or failed runs can be continued")
    if run_id in runner.active_run_ids():
        raise HTTPException(409, "The stopped crawler process is still shutting down")

    spec = get_crawler(run.crawler_id)
    params = json.loads(run.params or "{}")
    if spec is None or not spec.resolve_script(params.get("site")).exists():
        raise HTTPException(400, "Crawler script is unavailable")
    if not spec.supports_resume:
        raise HTTPException(409, "This crawler does not support continuing a previous run")
    if not spec.python.exists():
        raise HTTPException(400, "Crawler Python environment is unavailable")

    input_path = run_artifact_path(run, "input")
    if input_path is None:
        raise HTTPException(409, "The original input workbook is unavailable; this run cannot be continued")
    if spec.supports_resume and spec.resume_requires_output:
        output_path = run_artifact_path(run, "output")
        if output_path is None:
            raise HTTPException(409, "No partial output exists to resume; start a new run instead")
        if not is_zipfile(output_path):
            raise HTTPException(409, "The saved partial output is not a valid Excel workbook and cannot be resumed safely; restore a valid output or start a new run")

    params["fresh"] = False
    params["resume"] = run.crawler_id in {"ccc", "pacific-best"}
    run.params = json.dumps(params)
    run.status = "queued"
    run.error = None
    run.returncode = None
    run.pid = None
    run.waiting_for_human = False
    run.finished_at = None
    db.commit()
    db.refresh(run)

    runner.enqueue(run.id)
    resume_detail = "from its saved output" if spec.supports_resume else "from the next unfinished input row"
    log_activity(db, user, "continue_run", f"continued run #{run.id} {resume_detail}")
    return to_out(run, user)


@router.get("/runs/{run_id}/output")
def download_output(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    require_run_owner_or_admin(run, user)
    output_path = run_artifact_path(run, "output")
    if output_path is None:
        raise HTTPException(404, "No output file for this run")
    log_activity(db, user, "download_output", f"downloaded output for run #{run.id}")
    filename = f"{run.crawler_id}_run{run.id}.xlsx"
    return FileResponse(output_path, filename=filename)
