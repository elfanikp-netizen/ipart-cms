import json
import os
import shutil
import subprocess
import urllib.request
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from zipfile import is_zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import load_workbook
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..crawlers import CRAWLERS, InputSpec, get_crawler
from ..db import SessionLocal
from ..deps import get_current_user, log_activity
from ..input_files import (
    carid_input_mode,
    ccc_scenario_code_from_partslink,
    create_template,
    inspect_workbook,
    read_ccc_scenario_input,
    resolve_column_header,
    validate_input,
)
from ..models import Activity, CccScenario, Run, User, utcnow
from ..runner import runner
from ..schemas import ActivityPageOut, QueueOut, RunOut

router = APIRouter(prefix="/api", tags=["runs"])

ALLOWED_INPUT_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
CCC_SEARCH_BY_VIN_OEM = "vin_oem"
CCC_SEARCH_BY_VIN_PARTSLINK_SCENARIO = "vin_partslink_scenario"
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


def has_unfinished_google_vin_rows(output_path: Path | None) -> bool:
    if output_path is None:
        return False
    try:
        workbook = load_workbook(output_path, read_only=True, data_only=True)
        try:
            worksheet = workbook.active
            header = next(worksheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
            columns = {str(name).strip(): index for index, name in enumerate(header) if name is not None}
            required = ("Year", "Make", "Model")
            if any(name not in columns for name in required):
                return False
            status_index = columns.get("VIN_Status")
            completed_statuses = {"found", "not_found"}
            for row in worksheet.iter_rows(min_row=2, values_only=True):
                vehicle = (row[columns[name]] if columns[name] < len(row) else None for name in required)
                if any(value is None or not str(value).strip() for value in vehicle):
                    continue
                status = row[status_index] if status_index is not None and status_index < len(row) else None
                if str(status).strip() not in completed_statuses:
                    return True
            return False
        finally:
            workbook.close()
    except Exception:
        return False


def to_out(run: Run, user: User | None = None) -> RunOut:
    spec = get_crawler(run.crawler_id)
    params = json.loads(run.params or "{}")
    output_path = run_artifact_path(run, "output")
    incomplete_google_vin = (
        run.status == "success"
        and run.crawler_id == "vin-lookup"
        and params.get("site") == "google"
        and has_unfinished_google_vin_rows(output_path)
    )
    resumable_status = run.status in {"stopped", "failed"} or incomplete_google_vin
    out = RunOut.model_validate(run)
    out.crawler_name = spec.name if spec else run.crawler_id
    out.has_output = output_path is not None
    out.can_continue = (
        resumable_status
        and bool(spec and spec.supports_resume)
        and run_artifact_path(run, "input") is not None
        and spec is not None
        and spec.resolve_script(params.get("site"), params.get("input_mode")).is_file()
        and spec.python.is_file()
        and (not spec.resume_requires_output or output_path is not None)
        and (output_path is None or is_zipfile(output_path))
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


def resolve_ccc_scenarios(content: bytes, suffix: str, db: Session) -> tuple[list[str], dict[str, str]]:
    headers, rows = read_ccc_scenario_input(content, suffix)
    missing = [name.upper() for name in ("vin", "partslink") if name not in headers]
    if missing:
        return [f"Missing required header(s): {', '.join(missing)}."], {}
    if not rows:
        return ["The first worksheet has no data rows."], {}

    vin_index = headers.index("vin")
    partslink_index = headers.index("partslink")
    input_rows = []
    codes = set()
    errors = []
    for row_number, values in rows:
        vin = str(values[vin_index] or "").strip() if vin_index < len(values) else ""
        partslink = str(values[partslink_index] or "").strip() if partslink_index < len(values) else ""
        if not vin and not partslink:
            continue
        if not vin:
            errors.append(f"Row {row_number}: VIN is empty.")
            continue
        if not partslink:
            errors.append(f"Row {row_number}: PARTSLINK is empty.")
            continue
        code = ccc_scenario_code_from_partslink(partslink)
        if not code:
            errors.append(f"Row {row_number}: PARTSLINK '{partslink}' is too short to derive the scenario code.")
            continue
        input_rows.append((row_number, code))
        codes.add(code)
    if not input_rows and not errors:
        errors.append("The first worksheet has no VIN and PARTSLINK data rows.")

    records = db.scalars(
        select(CccScenario).where(CccScenario.part_code.in_(codes)).order_by(CccScenario.id)
    ).all() if codes else []
    found_codes = {record.part_code.strip() for record in records}
    scenarios = {
        record.part_code.strip(): record.scenario.strip()
        for record in records
        if record.scenario and record.scenario.strip()
    }
    for row_number, code in input_rows:
        if code not in found_codes:
            errors.append(f"Row {row_number}: Part Code {code} was not found in CCC Scenario.")
        elif not scenarios.get(code):
            errors.append(f"Row {row_number}: Scenario is empty for Part Code {code}.")
    return errors, scenarios


def add_ccc_scenario_column(content: bytes, suffix: str, scenarios: dict[str, str]) -> bytes:
    workbook = load_workbook(BytesIO(content), keep_vba=suffix == ".xlsm")
    try:
        worksheet = workbook.active
        header_columns = {
            "".join(character for character in str(cell.value or "").casefold() if character.isalnum()): cell.column
            for cell in worksheet[1]
        }
        partslink_index = header_columns.get("partslink")
        vin_index = header_columns.get("vin")
        if partslink_index is None or vin_index is None:
            raise HTTPException(400, "Input workbook must have VIN and PARTSLINK columns")
        scenario_index = header_columns.get("scenario", worksheet.max_column + 1)
        worksheet.cell(row=1, column=scenario_index, value="Scenario")
        for row_number in range(2, worksheet.max_row + 1):
            partslink = str(worksheet.cell(row=row_number, column=partslink_index).value or "").strip()
            code = ccc_scenario_code_from_partslink(partslink)
            worksheet.cell(row=row_number, column=scenario_index, value=scenarios.get(code, ""))
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()


@router.get("/crawlers")
def list_crawlers(_: User = Depends(get_current_user)):
    return [spec.to_dict() for spec in CRAWLERS.values()]


@router.get("/crawlers/{crawler_id}/template")
def download_input_template(
    crawler_id: str,
    site: str = "",
    search_action: str = CCC_SEARCH_BY_VIN_OEM,
    _: User = Depends(get_current_user),
):
    spec = get_crawler(crawler_id)
    if spec is None:
        raise HTTPException(404, f"Unknown crawler '{crawler_id}'")
    if crawler_id == "ccc" and search_action == CCC_SEARCH_BY_VIN_PARTSLINK_SCENARIO:
        spec = replace(spec, input_spec=InputSpec(
            required_headers=("VIN", "PARTSLINK"),
            template_headers=("VIN", "PARTSLINK"),
            hint="Use one vehicle and PARTSLINK value per row. CCC Scenario is filled automatically from the PARTSLINK code.",
        ))
    variant = spec.resolve_site(site)
    site_name = f"-{variant.key}" if variant else ""
    return StreamingResponse(
        BytesIO(create_template(spec, site)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{crawler_id}{site_name}-template.xlsx"'},
    )


@router.post("/input-preview")
async def preview_input(
    crawler_id: str = Form(...),
    file: UploadFile = File(...),
    column: str = Form(""),
    site: str = Form(""),
    search_action: str = Form(CCC_SEARCH_BY_VIN_OEM),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    spec = get_crawler(crawler_id)
    if spec is None:
        raise HTTPException(404, f"Unknown crawler '{crawler_id}'")
    suffix = Path(file.filename or "input.xlsx").suffix.lower()
    if suffix not in ALLOWED_INPUT_SUFFIXES:
        raise HTTPException(400, "Input must be an Excel file (.xlsx / .xlsm / .xls)")
    content = await file.read()
    try:
        headers, has_data = inspect_workbook(content, suffix)
    except Exception as error:
        return {"headers": [], "valid": False, "errors": [f"Could not read workbook: {error}"]}
    if crawler_id == "ccc" and search_action == CCC_SEARCH_BY_VIN_PARTSLINK_SCENARIO:
        if suffix not in {".xlsx", ".xlsm"}:
            errors = ["By VIN & PARTSLINK (Scenario) requires an .xlsx or .xlsm workbook."]
        else:
            errors, _ = resolve_ccc_scenarios(content, suffix, db)
    else:
        errors = validate_input(spec, site, column, headers, has_data)
    return {"headers": headers, "valid": not errors, "errors": errors}


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
    search_action: str = Form(CCC_SEARCH_BY_VIN_OEM),
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
    if crawler_id == "ccc" and search_action not in {
        CCC_SEARCH_BY_VIN_OEM,
        CCC_SEARCH_BY_VIN_PARTSLINK_SCENARIO,
    }:
        raise HTTPException(400, "Unknown CCC search action")
    if crawler_id != "ccc" and search_action != CCC_SEARCH_BY_VIN_OEM:
        raise HTTPException(400, "Search action is only available for CCC Workflow")
    if not spec.python.exists():
        raise HTTPException(400, f"Python env not found: {spec.python}")
    if spec.column_required and not column.strip():
        raise HTTPException(400, "This crawler requires a column value")

    suffix = Path(file.filename or "input.xlsx").suffix.lower()
    if suffix not in ALLOWED_INPUT_SUFFIXES:
        raise HTTPException(400, "Input must be an Excel file (.xlsx / .xlsm / .xls)")
    file_content = await file.read()
    try:
        headers, has_data = inspect_workbook(file_content, suffix)
    except Exception as error:
        raise HTTPException(400, f"Could not read input workbook: {error}") from error
    scenario_mapping = {}
    if crawler_id == "ccc" and search_action == CCC_SEARCH_BY_VIN_PARTSLINK_SCENARIO:
        if suffix not in {".xlsx", ".xlsm"}:
            raise HTTPException(400, "By VIN & PARTSLINK (Scenario) requires an .xlsx or .xlsm workbook")
        input_errors, scenario_mapping = resolve_ccc_scenarios(file_content, suffix, db)
    else:
        input_errors = validate_input(spec, site, column, headers, has_data)
    if input_errors:
        raise HTTPException(400, " ".join(input_errors))

    input_mode = carid_input_mode(headers, column) if spec.id == "carid" else ""
    script = spec.resolve_script(site, input_mode)
    if not script.exists():
        raise HTTPException(400, f"Script not found: {script}")

    params = {
        "column": column.strip(),
        "resolved_column": resolve_column_header(headers, column) or "",
        "site": site.strip(),
        "search_action": search_action,
        "input_mode": input_mode,
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
    if scenario_mapping:
        file_content = add_ccc_scenario_column(file_content, suffix, scenario_mapping)
    input_path.write_bytes(file_content)

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
    params = json.loads(run.params or "{}")
    output_path = run_artifact_path(run, "output")
    incomplete_google_vin = (
        run.status == "success"
        and run.crawler_id == "vin-lookup"
        and params.get("site") == "google"
        and has_unfinished_google_vin_rows(output_path)
    )
    if run.status not in {"stopped", "failed"} and not incomplete_google_vin:
        raise HTTPException(409, "Only stopped, failed, or incomplete Google VIN runs can be continued")
    if run_id in runner.active_run_ids():
        raise HTTPException(409, "The stopped crawler process is still shutting down")

    spec = get_crawler(run.crawler_id)
    if spec is None or not spec.resolve_script(params.get("site"), params.get("input_mode")).exists():
        raise HTTPException(400, "Crawler script is unavailable")
    if not spec.supports_resume:
        raise HTTPException(409, "This crawler does not support continuing a previous run")
    if not spec.python.exists():
        raise HTTPException(400, "Crawler Python environment is unavailable")

    input_path = run_artifact_path(run, "input")
    if input_path is None:
        raise HTTPException(409, "The original input workbook is unavailable; this run cannot be continued")
    if spec.supports_resume:
        if spec.resume_requires_output and output_path is None:
            raise HTTPException(409, "No partial output exists to resume; start a new run instead")
        if output_path is not None and not is_zipfile(output_path):
            raise HTTPException(409, "The saved partial output is not a valid Excel workbook and cannot be resumed safely; restore a valid output or start a new run")

    params["fresh"] = False
    params["resume"] = run.crawler_id in {"ccc", "pacific-best"}
    run.params = json.dumps(params)
    run.status = "queued"
    run.error = None
    run.returncode = None
    run.pid = None
    run.waiting_for_human = False
    run.progress_done = None
    run.progress_total = None
    run.finished_at = None
    db.commit()
    db.refresh(run)

    runner.enqueue(run.id)
    resume_detail = "from saved progress" if output_path else "from the original input"
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
