from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..config import settings
from ..deps import get_current_user, get_db, log_activity
from ..models import User
from ..schemas import LoginIn, UserOut
from ..security import create_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is inactive")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    log_activity(db, user, "login", "signed in" + (" (stay signed in)" if payload.remember else ""))
    ttl_days = 30 if payload.remember else 1
    response.set_cookie(
        "portal_session",
        create_token(user.id, user.username, user.role, remember=payload.remember),
        max_age=60 * 60 * 24 * ttl_days,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return UserOut.model_validate(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=204)
def logout(response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    log_activity(db, user, "logout", "signed out")
    response.delete_cookie("portal_session", path="/")