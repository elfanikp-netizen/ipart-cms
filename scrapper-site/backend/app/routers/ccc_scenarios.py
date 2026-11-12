from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db, log_activity
from ..models import CccScenario, User
from ..schemas import CccScenarioIn

router = APIRouter(prefix="/api/ccc-scenarios", tags=["CCC scenarios"])
PAGE_SIZE_MAX = 100


def record_out(item: CccScenario) -> dict:
    return {
        "id": item.id,
        "part_code": item.part_code,
        "part_description": item.part_description,
        "part_family": item.part_family,
        "scenario": item.scenario,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def normalize_payload(payload: CccScenarioIn) -> dict[str, str]:
    part_code = " ".join(payload.part_code.split())
    if not part_code:
        raise HTTPException(422, "Part Code is required")
    if len(part_code) > 150:
        raise HTTPException(422, "Part Code must be 150 characters or fewer")
    return {
        "part_code": part_code,
        "part_description": payload.part_description.strip(),
        "part_family": payload.part_family.strip(),
        "scenario": payload.scenario.strip(),
    }


@router.get("/records")
def list_records(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=PAGE_SIZE_MAX),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(CccScenario)
    if search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(
            CccScenario.part_code.ilike(pattern),
            CccScenario.part_description.ilike(pattern),
            CccScenario.part_family.ilike(pattern),
            CccScenario.scenario.ilike(pattern),
        ))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(
        stmt.order_by(CccScenario.part_code, CccScenario.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [record_out(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("/records", status_code=201)
def create_record(
    payload: CccScenarioIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = CccScenario(**normalize_payload(payload))
    db.add(item)
    db.commit()
    db.refresh(item)
    log_activity(db, user, "create_ccc_scenario", f"created Part Code {item.part_code}")
    return record_out(item)


@router.put("/records/{record_id}")
def update_record(
    record_id: int,
    payload: CccScenarioIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(CccScenario, record_id)
    if item is None:
        raise HTTPException(404, "CCC Scenario record not found")
    for field, value in normalize_payload(payload).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    log_activity(db, user, "update_ccc_scenario", f"updated record {record_id}")
    return record_out(item)


@router.delete("/records/{record_id}", status_code=204)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(CccScenario, record_id)
    if item is None:
        raise HTTPException(404, "CCC Scenario record not found")
    part_code = item.part_code
    db.delete(item)
    db.commit()
    log_activity(db, user, "delete_ccc_scenario", f"deleted Part Code {part_code}")
