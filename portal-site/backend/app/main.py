from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, SessionLocal, ensure_database_schema, engine
from .models import User
from .routers import auth, users
from .security import hash_password


def seed_superadmin() -> None:
    with SessionLocal() as db:
        if db.query(User).filter(User.username == "superadmin").first() is None:
            db.add(
                User(
                    username="superadmin",
                    password_hash=hash_password("12345678"),
                    display_name="Super Admin",
                    role="superadmin",
                    is_active=True,
                )
            )
            db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_database_schema()
    Base.metadata.create_all(engine)
    seed_superadmin()
    yield


app = FastAPI(title="Portal Identity", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/api/health")
def health():
    return {"ok": True}