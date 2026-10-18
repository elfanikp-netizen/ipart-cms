from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..deps import get_current_user, log_activity, require_superadmin
from ..models import Activity, User
from ..schemas import ActivityOut, UserCreate, UserOut, UserUpdate
from ..security import hash_password

router = APIRouter(prefix="/api", tags=["users"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------------------------------------------- users
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
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_activity(db, admin, "create_user", f"created {user.username} ({user.role})")
    return user


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_superadmin)):
    user = db.get(User, user_id)
    if not user:
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
        user.role = payload.role
        changes.append(f"role={payload.role}")
    if payload.is_active is not None:
        # never let the last active superadmin lock everyone out
        if not payload.is_active and user.role == "superadmin":
            others = db.query(User).filter(User.role == "superadmin", User.is_active.is_(True), User.id != user.id).count()
            if others == 0:
                raise HTTPException(400, "Cannot deactivate the last active superadmin")
        user.is_active = payload.is_active
        changes.append(f"is_active={payload.is_active}")
    db.commit()
    db.refresh(user)
    if changes:
        log_activity(db, admin, "update_user", f"{user.username}: {', '.join(changes)}")
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_superadmin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "You cannot delete your own account")
    if user.role == "superadmin":
        others = db.query(User).filter(User.role == "superadmin", User.id != user.id).count()
        if others == 0:
            raise HTTPException(400, "Cannot delete the last superadmin")
    db.delete(user)
    db.commit()
    log_activity(db, admin, "delete_user", f"deleted {user.username}")


# ---------------------------------------------------------------- activity
def to_activity_out(a: Activity) -> ActivityOut:
    return ActivityOut(
        id=a.id,
        user_id=a.user_id,
        username=a.user.username if a.user else "?",
        action=a.action,
        detail=a.detail or "",
        created_at=a.created_at,
    )


@router.get("/activity", response_model=list[ActivityOut])
def all_activity(
    limit: int = 100,
    q: str = "",
    username: str = "",
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    stmt = select(Activity).order_by(Activity.id.desc())

    if me.role == "superadmin":
        # superadmin sees everything; optionally narrow to one user
        if username.strip():
            stmt = stmt.join(User, Activity.user_id == User.id, isouter=True).where(
                User.username == username.strip()
            )
    else:
        # regular users only ever see their own activity
        stmt = stmt.where(Activity.user_id == me.id)

    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Activity.action.like(like), Activity.detail.like(like)))

    rows = db.scalars(stmt.limit(limit)).all()
    return [to_activity_out(a) for a in rows]


@router.get("/users/{user_id}/activity", response_model=list[ActivityOut])
def user_activity(user_id: int, limit: int = 100, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    if me.role != "superadmin" and me.id != user_id:
        raise HTTPException(403, "You can only view your own activity")
    rows = db.scalars(
        select(Activity).where(Activity.user_id == user_id).order_by(Activity.id.desc()).limit(limit)
    ).all()
    return [to_activity_out(a) for a in rows]
