from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, SessionLocal, engine
from .models import User
from .routers import auth, runs, users
from .runner import runner
from .security import hash_password


def seed_superadmin() -> None:
    """Create the default superadmin account on first startup."""
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


def migrate_columns() -> None:
    """Add columns introduced after the initial schema (lightweight, SQLite)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "runs" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("runs")}
    wanted = {
        "user_id": "INTEGER",
        "progress_done": "INTEGER",
        "progress_total": "INTEGER",
    }
    with engine.begin() as conn:
        for name, coltype in wanted.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE runs ADD COLUMN {name} {coltype}"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    migrate_columns()
    seed_superadmin()
    runner.start()
    yield


app = FastAPI(title="Scraper CMS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(runs.router)
app.include_router(users.router)


@app.get("/api/health")
def health():
    return {"ok": True}
