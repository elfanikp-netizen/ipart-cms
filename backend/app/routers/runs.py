import json
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


@router.post("/runs", response_model=RunOut, status_code=201)
async def create_run(
    crawler_id: str = Form(...),
    file: UploadFile = File(...),
    column: str = Form(""),
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
    if not spec.script.exists():
        raise HTTPException(400, f"Script not found: {spec.script}")
    if not spec.python.exists():
        raise HTTPException(400, f"Python env not found: {spec.python}")
    if spec.column_required and not column.strip():
        raise HTTPException(400, "This crawler requires a column value")

    suffix = Path(file.filename or "input.xlsx").suffix.lower()
    if suffix not in ALLOWED_INPUT_SUFFIXES:
        raise HTTPException(400, "Input must be an Excel file (.xlsx / .xlsm / .xls)")

    params = {
        "column": column.strip(),
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
    log_activity(db, user, "create_run", f"queued {spec.name} (run #{run.id})")
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
