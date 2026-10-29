from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, SessionLocal, engine, ensure_database_schema, migrate_user_app_access
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
        for table in ("users",):
            if table in legacy_tables and table not in shared_tables:
                quoted_table = preparer.quote(table)
                connection.execute(
                    text(f"ALTER TABLE {legacy_schema}.{quoted_table} SET SCHEMA {shared_schema}")
                )


def migrate_scraper_activities() -> None:
    if engine.dialect.name != "postgresql":
        return

    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    available_schemas = set(inspector.get_schema_names())
    source_schemas = ["global"]
    if settings.database_schema != "global" and settings.database_schema in available_schemas:
        source_schemas.append(settings.database_schema)
    with engine.begin() as connection:
        if "activities" not in inspector.get_table_names(schema="global"):
            connection.execute(text(
                "CREATE TABLE global.activities ("
                "id SERIAL PRIMARY KEY, user_id INTEGER NULL, action VARCHAR(30) NOT NULL, "
                "detail TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            ))
        for source_schema in source_schemas:
            if "activities" not in inspector.get_table_names(schema=source_schema):
                continue
            source_table = f'{engine.dialect.identifier_preparer.quote_schema(source_schema)}."activities"'
            connection.execute(text(
                "INSERT INTO scrapping.activities (user_id, action, detail, created_at) "
                "SELECT source.user_id, source.action, source.detail, source.created_at "
                f"FROM {source_table} AS source "
                "WHERE source.action IN ('create_run', 'stop_run', 'continue_run', 'run_success', 'run_failed', "
                "'run_stopped', 'download_output', 'show_browser', 'hide_browser') "
                "AND NOT EXISTS (SELECT 1 FROM scrapping.activities AS target "
                "WHERE target.user_id IS NOT DISTINCT FROM source.user_id "
                "AND target.action = source.action AND target.detail = source.detail "
                "AND target.created_at = source.created_at)"
            ))
            if source_schema != "scrapping":
                connection.execute(text(
                    f"DELETE FROM {source_table} WHERE action IN "
                    "('create_run', 'stop_run', 'continue_run', 'run_success', 'run_failed', "
                    "'run_stopped', 'download_output', 'show_browser', 'hide_browser')"
                ))
            if source_schema != "global":
                connection.execute(text(
                    f"INSERT INTO global.activities (user_id, action, detail, created_at) "
                    f"SELECT source.user_id, source.action, source.detail, source.created_at FROM {source_table} AS source "
                    "WHERE source.action IN ('login', 'logout', 'update_profile', 'create_user', 'update_user', 'delete_user') "
                    "AND NOT EXISTS (SELECT 1 FROM global.activities AS target "
                    "WHERE target.user_id IS NOT DISTINCT FROM source.user_id "
                    "AND target.action = source.action AND target.detail = source.detail "
                    "AND target.created_at = source.created_at)"
                ))
                connection.execute(text(
                    f"DELETE FROM {source_table} WHERE action IN "
                    "('login', 'logout', 'update_profile', 'create_user', 'update_user', 'delete_user')"
                ))


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_database_schema()
    migrate_identity_schema()
    Base.metadata.create_all(engine)
    migrate_user_app_access()
    migrate_columns()
    migrate_scraper_activities()
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
