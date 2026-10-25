import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 24
TOKEN_TTL_HOURS_REMEMBER = 24 * 30


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}${password}".encode()).hexdigest()
    return f"sha256${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    candidate = hashlib.sha256(f"{salt}${password}".encode()).hexdigest()
    return secrets.compare_digest(candidate, digest)


def create_token(user_id: int, username: str, role: str, remember: bool = False) -> str:
    now = datetime.now(timezone.utc)
    ttl = TOKEN_TTL_HOURS_REMEMBER if remember else TOKEN_TTL_HOURS
    return jwt.encode(
        {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "iat": now,
            "exp": now + timedelta(hours=ttl),
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])