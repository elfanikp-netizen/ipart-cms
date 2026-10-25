from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import SessionLocal
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class PortalUser:
    id: int
    is_active: bool


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> PortalUser:
    token = credentials.credentials if credentials else request.cookies.get("portal_session")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except Exception as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session") from error
    user_table = '"global"."users"' if db.bind and db.bind.dialect.name == "postgresql" else '"users"'
    user_row = db.execute(text(f"SELECT id, is_active FROM {user_table} WHERE id = :user_id"),
                          {"user_id": user_id}).mappings().first()
    if user_row is None or not user_row["is_active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled or removed")
    return PortalUser(id=user_row["id"], is_active=user_row["is_active"])