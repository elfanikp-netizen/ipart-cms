import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth import PortalUser, get_current_user, get_db
from ..schemas import ActivityPageOut

router = APIRouter(prefix="/api/universe/activity", tags=["activity"])


@router.get("", response_model=ActivityPageOut)
def list_activity(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str = "",
    username: str = "",
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    activity_table = '"universe"."activities"' if db.bind and db.bind.dialect.name == "postgresql" else '"universe_activities"'
    user_table = '"global"."users"' if db.bind and db.bind.dialect.name == "postgresql" else '"users"'
    filters = []
    filters_params: dict[str, object] = {}
    if user.role != "superadmin":
        filters.append("a.user_id = :user_id")
        filters_params["user_id"] = user.id
    elif username.strip():
        filters.append("u.username = :username")
        filters_params["username"] = username.strip()
    if search.strip():
        filters.append("(lower(a.action) LIKE :search OR lower(a.detail) LIKE :search OR lower(u.username) LIKE :search)")
        filters_params["search"] = f"%{search.strip().lower()}%"
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    count_sql = text(
        f"SELECT count(*) FROM {activity_table} AS a LEFT JOIN {user_table} AS u ON u.id = a.user_id {where_clause}"
    )
    total = db.execute(count_sql, filters_params).scalar_one()
    rows_params = {**filters_params, "limit": page_size, "offset": (page - 1) * page_size}
    rows = db.execute(text(
        f"SELECT a.id, a.user_id, coalesce(u.username, '?') AS username, a.action, a.detail, a.created_at "
        f"FROM {activity_table} AS a LEFT JOIN {user_table} AS u ON u.id = a.user_id {where_clause} "
        "ORDER BY a.id DESC LIMIT :limit OFFSET :offset"
    ), rows_params).mappings().all()
    return {
        "items": [dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": math.ceil(total / page_size) if total else 0,
    }