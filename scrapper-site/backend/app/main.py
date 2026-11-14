from contextlib import asynccontextmanager
from datetime import datetime
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, SessionLocal, engine, ensure_database_schema, migrate_user_app_access
from .models import CccScenario
from .routers import ccc_scenarios, runs
from .runner import runner


def migrate_columns() -> None:
    """Add columns and indexes introduced after the initial schema."""
    from sqlalchemy import inspect, text

    schema = settings.database_schema if engine.dialect.name == "postgresql" else None
    insp = inspect(engine)
    if "runs" not in insp.get_table_names(schema=schema):
        return
    existing = {c["name"] for c in insp.get_columns("runs", schema=schema)}
    wanted = {
        "user_id": "INTEGER",
        "progress_done": "INTEGER",
        "progress_total": "INTEGER",
        "idempotency_key": "VARCHAR(64)",
    }
    indexes = {index["name"] for index in insp.get_indexes("runs", schema=schema)}
    constraints = {item.get("name") for item in insp.get_unique_constraints("runs", schema=schema)}
    preparer = engine.dialect.identifier_preparer
    table_name = preparer.quote("runs")
    table = f"{preparer.quote_schema(schema)}.{table_name}" if schema else table_name
    index_name = "uq_runs_user_idempotency_key"
    index = preparer.quote(index_name)
    with engine.begin() as conn:
        for name, coltype in wanted.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {preparer.quote(name)} {coltype}"))
        if index_name not in indexes and index_name not in constraints:
            conn.execute(text(
                f"CREATE UNIQUE INDEX {index} ON {table} (user_id, idempotency_key)"
            ))


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


def migrate_ccc_scenarios() -> None:
    if engine.dialect.name not in {"postgresql", "sqlite"}:
        return

    from sqlalchemy import inspect, text

    schema = "scrapping" if engine.dialect.name == "postgresql" else None
    inspector = inspect(engine)
    tables = set(inspector.get_table_names(schema=schema))
    preparer = engine.dialect.identifier_preparer

    def qualified(name: str) -> str:
        table_name = preparer.quote(name)
        return f"{preparer.quote_schema(schema)}.{table_name}" if schema else table_name

    def normalized_timestamp(value):
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value

    legacy_name = "ccc_scenarios_import_legacy"
    if "ccc_scenarios" in tables:
        columns = {column["name"] for column in inspector.get_columns("ccc_scenarios", schema=schema)}
        if {"file_id", "data"}.issubset(columns) and legacy_name not in tables:
            with engine.begin() as connection:
                connection.execute(text(
                    f"ALTER TABLE {qualified('ccc_scenarios')} "
                    f"RENAME TO {preparer.quote(legacy_name)}"
                ))
            tables.remove("ccc_scenarios")
            tables.add(legacy_name)

    with engine.begin() as connection:
        CccScenario.__table__.create(connection, checkfirst=True)
        destination = CccScenario.__table__
        if legacy_name in tables:
            old_rows = connection.execute(text(
                f"SELECT data, created_at, updated_at FROM {qualified(legacy_name)} ORDER BY id"
            )).mappings().all()
            values = []
            for row in old_rows:
                data = row["data"] or {}
                if isinstance(data, str):
                    data = json.loads(data)
                values.append({
                    "part_code": str(data.get("Part Code") or "").strip(),
                    "part_description": str(data.get("Part Description") or "").strip(),
                    "part_family": str(data.get("Part Family") or "").strip(),
                    "scenario": str(data.get("Scenario") or "").strip(),
                    "created_at": normalized_timestamp(row["created_at"]),
                    "updated_at": normalized_timestamp(row["updated_at"]),
                })
            if values:
                connection.execute(destination.insert(), values)

        if "ccc_scenario_codes" in tables:
            codes = connection.execute(text(
                f"SELECT partslink_code, created_at, updated_at "
                f"FROM {qualified('ccc_scenario_codes')} ORDER BY id"
            )).all()
            if codes:
                connection.execute(destination.insert(), [{
                    "part_code": code,
                    "part_description": "",
                    "part_family": "",
                    "scenario": "",
                    "created_at": normalized_timestamp(created_at),
                    "updated_at": normalized_timestamp(updated_at),
                } for code, created_at, updated_at in codes])
            connection.execute(text(f"DROP TABLE {qualified('ccc_scenario_codes')}"))

        if legacy_name in tables:
            connection.execute(text(f"DROP TABLE {qualified(legacy_name)}"))
        if "ccc_scenarios" in tables and legacy_name not in tables:
            columns = {column["name"] for column in inspector.get_columns("ccc_scenarios", schema=schema)}
            if {"file_id", "data"}.issubset(columns):
                connection.execute(text(f"DROP TABLE {qualified('ccc_scenarios')}"))
        if "ccc_scenario_files" in tables:
            connection.execute(text(f"DROP TABLE {qualified('ccc_scenario_files')}"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_database_schema()
    migrate_identity_schema()
    migrate_ccc_scenarios()
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
app.include_router(ccc_scenarios.router)


@app.get("/api/health")
def health():
    return {"ok": True}
