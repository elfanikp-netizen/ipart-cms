from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, SessionLocal, engine, ensure_database_schema
from .routers import runs
from .runner import runner


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


def migrate_identity_schema() -> None:
    """Move existing identity records from the app schema to the shared schema."""
    if engine.dialect.name != "postgresql" or settings.database_schema == "global":
        return

    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    shared_tables = set(inspector.get_table_names(schema="global"))
    legacy_tables = set(inspector.get_table_names(schema=settings.database_schema))
    preparer = engine.dialect.identifier_preparer
    shared_schema = preparer.quote_schema("global")
    legacy_schema = preparer.quote_schema(settings.database_schema)
    with engine.begin() as connection:
        for table in ("users", "activities"):
            if table in legacy_tables and table not in shared_tables:
                quoted_table = preparer.quote(table)
                connection.execute(
                    text(f"ALTER TABLE {legacy_schema}.{quoted_table} SET SCHEMA {shared_schema}")
                )


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_database_schema()
    migrate_identity_schema()
    Base.metadata.create_all(engine)
    migrate_columns()
    runner.start()
    yield


app = FastAPI(title="Scraper CMS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(runs.router)


@app.get("/api/health")
def health():
    return {"ok": True}
