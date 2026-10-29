import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db, log_activity, require_superadmin
from ..models import Activity, User
from ..schemas import ActivityOut, ActivityPageOut, ProfileUpdate, UserCreate, UserOut, UserUpdate
from ..security import hash_password, verify_password

router = APIRouter(prefix="/api", tags=["users", "activity"])


@router.get("/profile", response_model=UserOut)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/profile", response_model=UserOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    user = db.get(User, me.id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Account is disabled or no longer exists")
    changed: list[str] = []
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()[:100]
        changed.append("display_name")
    if payload.new_password:
        if not payload.current_password or not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(400, "Current password is incorrect")
        if len(payload.new_password) < 8:
            raise HTTPException(400, "New password must be at least 8 characters")
        user.password_hash = hash_password(payload.new_password)
        changed.append("password")
    elif payload.current_password:
        raise HTTPException(400, "Provide a new password to change your password")
    if not changed:
        raise HTTPException(400, "No profile changes supplied")
    db.commit()
    db.refresh(user)
    log_activity(db, user, "update_profile", f"updated {', '.join(changed)}")
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_superadmin)):
    if payload.role not in ("user", "superadmin"):
        raise HTTPException(400, "role must be 'user' or 'superadmin'")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(409, "Username already exists")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        is_active=True,
        app_access=payload.app_access or ({"scraper": True, "universe": True} if payload.role == "superadmin" else {"scraper": True, "universe": False}),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_activity(db, admin, "create_user", f"created {user.username} ({user.role})")
    return user


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_superadmin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    changes: list[str] = []
    if payload.password:
        user.password_hash = hash_password(payload.password)
        changes.append("password")
    if payload.display_name is not None:
        user.display_name = payload.display_name
        changes.append("display_name")
    if payload.role is not None:
        if payload.role not in ("user", "superadmin"):
            raise HTTPException(400, "role must be 'user' or 'superadmin'")
        if user.role == "superadmin" and user.is_active and payload.role != "superadmin":
            others = db.query(User).filter(User.role == "superadmin", User.is_active.is_(True), User.id != user.id).count()
            if others == 0:
                raise HTTPException(400, "Cannot demote the last active superadmin")
        user.role = payload.role
        changes.append(f"role={payload.role}")
    if payload.is_active is not None:
        if not payload.is_active and user.role == "superadmin":
            others = db.query(User).filter(User.role == "superadmin", User.is_active.is_(True), User.id != user.id).count()
            if others == 0:
                raise HTTPException(400, "Cannot deactivate the last active superadmin")
        user.is_active = payload.is_active
        changes.append(f"is_active={payload.is_active}")
    if payload.app_access is not None:
        unknown_apps = set(payload.app_access) - {"scraper", "universe"}
        if unknown_apps or any(not isinstance(value, bool) for value in payload.app_access.values()):
            raise HTTPException(400, "app_access must contain scraper/universe boolean values")
        user.app_access = {
            "scraper": bool(payload.app_access.get("scraper", False)),
            "universe": bool(payload.app_access.get("universe", False)),
        }
        changes.append(f"app_access={user.app_access}")
    db.commit()
    db.refresh(user)
    if changes:
        log_activity(db, admin, "update_user", f"{user.username}: {', '.join(changes)}")
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_superadmin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "You cannot delete your own account")
    if user.role == "superadmin":
        others = db.query(User).filter(User.role == "superadmin", User.id != user.id).count()
        if others == 0:
            raise HTTPException(400, "Cannot delete the last superadmin")
    username = user.username
    db.delete(user)
    db.commit()
    log_activity(db, admin, "delete_user", f"deleted {username}")


def to_activity_out(activity: Activity) -> ActivityOut:
    return ActivityOut(
        id=activity.id,
        user_id=activity.user_id,
        username=activity.user.username if activity.user else "?",
        action=activity.action,
        detail=activity.detail or "",
        created_at=activity.created_at,
    )


@router.get("/activity", response_model=list[ActivityOut])
def all_activity(
    limit: int = 100,
    q: str = "",
    username: str = "",
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    stmt = select(Activity).where(Activity.action.notin_(("create_run", "stop_run", "continue_run"))).order_by(Activity.id.desc())
    if me.role == "superadmin":
        if username.strip():
            stmt = stmt.where(Activity.user.has(User.username == username.strip()))
    else:
        stmt = stmt.where(Activity.user_id == me.id)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Activity.action.like(like), Activity.detail.like(like)))
    return [to_activity_out(activity) for activity in db.scalars(stmt.limit(limit)).all()]


@router.get("/activity/page", response_model=ActivityPageOut)
def activity_page(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str = "",
    username: str = "",
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    stmt = select(Activity).where(Activity.action.notin_(("create_run", "stop_run", "continue_run")))
    if me.role == "superadmin":
        if username.strip():
            stmt = stmt.where(Activity.user.has(User.username == username.strip()))
    else:
        stmt = stmt.where(Activity.user_id == me.id)
    if search.strip():
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(Activity.action.ilike(like), Activity.detail.ilike(like), Activity.user.has(User.username.ilike(like)))
        )
    count = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.order_by(Activity.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [to_activity_out(activity) for activity in rows],
        "page": page,
        "page_size": page_size,
        "total": count,
        "pages": math.ceil(count / page_size) if count else 0,
    }


@router.get("/users/{user_id}/activity", response_model=list[ActivityOut])
def user_activity(user_id: int, limit: int = 100, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    if me.role != "superadmin" and me.id != user_id:
        raise HTTPException(403, "You can only view your own activity")
    rows = db.scalars(
        select(Activity)
        .where(
            Activity.user_id == user_id,
            Activity.action.notin_(("create_run", "stop_run", "continue_run")),
        )
        .order_by(Activity.id.desc())
        .limit(limit)
    ).all()
    return [to_activity_out(activity) for activity in rows]