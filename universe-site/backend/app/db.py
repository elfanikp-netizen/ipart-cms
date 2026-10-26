import json

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

settings.data_dir.mkdir(parents=True, exist_ok=True)
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def set_connection_options(dbapi_conn, _):
    if engine.dialect.name == "sqlite":
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
    elif engine.dialect.name == "postgresql":
        preparer = engine.dialect.identifier_preparer
        universe_schema = preparer.quote_schema("universe")
        global_schema = preparer.quote_schema("global")
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET search_path TO {universe_schema}, {global_schema}, public")
        cursor.close()
        dbapi_conn.commit()


def ensure_database_schema() -> None:
    if engine.dialect.name == "postgresql":
        quoted = engine.dialect.identifier_preparer.quote_schema("universe")
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quoted}"))


def migrate_vin_uniqueness() -> None:
    inspector = inspect(engine)
    schema = "universe" if engine.dialect.name == "postgresql" else None
    constraints = inspector.get_unique_constraints("vin", schema=schema)
    old_constraints = [
        item["name"] for item in constraints
        if item.get("column_names") == ["vin_key"] and item.get("name")
    ]
    has_vehicle_constraint = any(
        item.get("column_names") == ["id_vehicle", "vin_key"]
        for item in constraints
    )

    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            preparer = engine.dialect.identifier_preparer
            table = f"{preparer.quote_schema(schema)}.{preparer.quote('vin')}"
            for name in old_constraints:
                connection.execute(text(
                    f"ALTER TABLE {table} DROP CONSTRAINT {preparer.quote(name)}"
                ))
            if not has_vehicle_constraint:
                connection.execute(text(
                    f"ALTER TABLE {table} ADD CONSTRAINT uq_vin_vehicle_vin "
                    "UNIQUE (id_vehicle, vin_key)"
                ))
    elif engine.dialect.name == "sqlite" and old_constraints:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE vin_new ("
                "id INTEGER NOT NULL PRIMARY KEY, "
                "id_vehicle INTEGER NOT NULL REFERENCES vehicle(id) ON DELETE CASCADE, "
                "vin VARCHAR(32) NOT NULL, vin_key VARCHAR(32) NOT NULL, "
                "notes TEXT NOT NULL, created_at DATETIME NOT NULL, "
                "updated_at DATETIME NOT NULL, created_by INTEGER, updated_by INTEGER, "
                "CONSTRAINT uq_vin_vehicle_vin UNIQUE (id_vehicle, vin_key))"
            )
            connection.exec_driver_sql(
                "INSERT INTO vin_new SELECT id, id_vehicle, vin, vin_key, notes, "
                "created_at, updated_at, created_by, updated_by FROM vin"
            )
            connection.exec_driver_sql("DROP TABLE vin")
            connection.exec_driver_sql("ALTER TABLE vin_new RENAME TO vin")
            connection.exec_driver_sql("CREATE INDEX ix_vin_id_vehicle ON vin (id_vehicle)")
            connection.exec_driver_sql("CREATE INDEX ix_vin_vin_key ON vin (vin_key)")


def migrate_ccc_market_rows() -> None:
    if engine.dialect.name != "postgresql":
        return

    schema = "universe"
    inspector = inspect(engine)
    constraints = inspector.get_unique_constraints("ccc_market_data", schema=schema)
    crawl_key_constraints = [
        item["name"] for item in constraints
        if item.get("column_names") == ["oem", "vin", "crawl_date"] and item.get("name")
    ]
    has_offer_key = any(
        item.get("column_names") == ["oem", "vin", "crawl_date", "market_index"]
        for item in constraints
    )
    columns = {column["name"] for column in inspector.get_columns("ccc_market_data", schema=schema)}

    with engine.begin() as connection:
        preparer = engine.dialect.identifier_preparer
        table = f"{preparer.quote_schema(schema)}.{preparer.quote('ccc_market_data')}"
        if "market_index" not in columns:
            connection.execute(text(
                f"ALTER TABLE {table} ADD COLUMN market_index INTEGER NOT NULL DEFAULT 0"
            ))
        for name in crawl_key_constraints:
            connection.execute(text(
                f"ALTER TABLE {table} DROP CONSTRAINT {preparer.quote(name)}"
            ))
        if not has_offer_key:
            connection.execute(text(
                f"ALTER TABLE {table} ADD CONSTRAINT uq_ccc_market_oem_vin_date_index "
                "UNIQUE (oem, vin, crawl_date, market_index)"
            ))


def migrate_user_app_access() -> None:
    schema = "global" if engine.dialect.name == "postgresql" else None
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names(schema=schema):
        return
    columns = {column["name"] for column in inspector.get_columns("users", schema=schema)}
    preparer = engine.dialect.identifier_preparer
    table = f"{preparer.quote_schema(schema)}.{preparer.quote('users')}" if schema else preparer.quote("users")
    with engine.begin() as connection:
        if "app_access" not in columns:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN app_access JSON"))
        rows = connection.execute(text(f"SELECT id, role FROM {table} WHERE app_access IS NULL")).all()
        for user_id, role in rows:
            access = {"scraper": True, "universe": role == "superadmin"}
            if engine.dialect.name == "postgresql":
                connection.execute(text(f"UPDATE {table} SET app_access = CAST(:access AS JSON) WHERE id = :id"),
                                   {"access": json.dumps(access), "id": user_id})
            else:
                connection.execute(text(f"UPDATE {table} SET app_access = :access WHERE id = :id"),
                                   {"access": json.dumps(access), "id": user_id})


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()