import json

from sqlalchemy import create_engine, event, inspect, select, text, update
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


def prepare_oem_relationship_migration() -> None:
    schema = "universe" if engine.dialect.name == "postgresql" else None
    inspector = inspect(engine)
    tables = set(inspector.get_table_names(schema=schema))
    if "oem" not in tables or "oem_legacy" in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("oem", schema=schema)}
    if "id_vin" not in columns:
        return

    preparer = engine.dialect.identifier_preparer
    table = f"{preparer.quote_schema(schema)}.{preparer.quote('oem')}" if schema else preparer.quote("oem")
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table} RENAME TO {preparer.quote('oem_legacy')}"))
        if engine.dialect.name == "postgresql":
            sequence = connection.execute(text(
                "SELECT to_regclass('universe.oem_id_seq')"
            )).scalar_one_or_none()
            if sequence is not None:
                connection.execute(text(
                    "ALTER SEQUENCE universe.oem_id_seq RENAME TO oem_legacy_id_seq"
                ))


def migrate_oem_relationships() -> None:
    from . import models

    schema = "universe" if engine.dialect.name == "postgresql" else None
    inspector = inspect(engine)
    if "oem_legacy" not in inspector.get_table_names(schema=schema):
        return

    preparer = engine.dialect.identifier_preparer
    def qualified(name: str) -> str:
        return f"{preparer.quote_schema(schema)}.{preparer.quote(name)}" if schema else preparer.quote(name)

    legacy = qualified("oem_legacy")
    oem_table = qualified("oem")
    oem_vin_table = qualified("oem_vin")
    with engine.connect() as connection:
        rows = connection.execute(text(
            f"SELECT id, id_vin, oem, oem_key, description, notes, created_at, updated_at, "
            f"created_by, updated_by FROM {legacy} ORDER BY id"
        )).mappings().all()

    grouped: dict[str, list] = {}
    for row in rows:
        key = " ".join(str(row["oem_key"] or row["oem"] or "").split()).casefold()
        grouped.setdefault(key, []).append(row)

    with engine.begin() as connection:
        for key, group in grouped.items():
            descriptions = list(dict.fromkeys(str(row["description"] or "").strip() for row in group if str(row["description"] or "").strip()))
            notes = list(dict.fromkeys(str(row["notes"] or "").strip() for row in group if str(row["notes"] or "").strip()))
            newest = max(group, key=lambda row: str(row["updated_at"] or ""))
            existing_id = connection.execute(
                text(f"SELECT id FROM {oem_table} WHERE oem_key = :key"), {"key": key}
            ).scalar_one_or_none()
            if existing_id is None:
                existing_id = group[0]["id"]
                connection.execute(text(
                    f"INSERT INTO {oem_table} "
                    "(id, oem, oem_key, description, notes, created_at, updated_at, created_by, updated_by) "
                    "VALUES (:id, :oem, :key, :description, :notes, :created_at, :updated_at, :created_by, :updated_by)"
                ), {
                    "id": existing_id,
                    "oem": group[0]["oem"],
                    "key": key,
                    "description": "\n".join(descriptions),
                    "notes": "\n".join(notes),
                    "created_at": min((row["created_at"] for row in group if row["created_at"] is not None), default=None),
                    "updated_at": newest["updated_at"],
                    "created_by": next((row["created_by"] for row in group if row["created_by"] is not None), None),
                    "updated_by": newest["updated_by"],
                })
            linked_vins: set[int] = set()
            for row in group:
                vin_id = row["id_vin"]
                if vin_id in linked_vins:
                    continue
                linked_vins.add(vin_id)
                connection.execute(text(
                    f"INSERT INTO {oem_vin_table} (id_oem, id_vin) VALUES (:id_oem, :id_vin)"
                ), {"id_oem": existing_id, "id_vin": vin_id})

        connection.execute(text(f"DROP TABLE {legacy}"))
        if engine.dialect.name == "postgresql":
            connection.execute(text(
                "SELECT setval(pg_get_serial_sequence('universe.oem', 'id'), "
                "COALESCE((SELECT MAX(id) FROM universe.oem), 1), "
                "EXISTS (SELECT 1 FROM universe.oem))"
            ))


def ensure_partslink_interchange_view() -> None:
    if engine.dialect.name == "postgresql":
        statement = """
            CREATE OR REPLACE VIEW universe.v_partslink_interchange AS
            SELECT
                p.id AS id_partslink,
                p.partslink,
                i.id AS id_interchange,
                i.interchange,
                COUNT(DISTINCT o.id) AS distinct_oem_count
            FROM universe.oem_partslink AS op
            JOIN universe.oem_interchange AS oi ON oi.id_oem = op.id_oem
            JOIN universe.oem AS o ON o.id = op.id_oem
            JOIN universe.partslink AS p ON p.id = op.id_partslink
            JOIN universe.interchange AS i ON i.id = oi.id_interchange
            GROUP BY p.id, p.partslink, i.id, i.interchange
        """
    elif engine.dialect.name == "sqlite":
        statement = """
            CREATE VIEW IF NOT EXISTS v_partslink_interchange AS
            SELECT
                p.id AS id_partslink,
                p.partslink,
                i.id AS id_interchange,
                i.interchange,
                COUNT(DISTINCT o.id) AS distinct_oem_count
            FROM oem_partslink AS op
            JOIN oem_interchange AS oi ON oi.id_oem = op.id_oem
            JOIN oem AS o ON o.id = op.id_oem
            JOIN partslink AS p ON p.id = op.id_partslink
            JOIN interchange AS i ON i.id = oi.id_interchange
            GROUP BY p.id, p.partslink, i.id, i.interchange
        """
    else:
        return
    with engine.begin() as connection:
        connection.execute(text(statement))


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


def migrate_oem_vin_validity() -> None:
    from .models import OEM_VIN, CccMarketRecord, Oem, Vin
    from .routers.master_data import normalized_key

    schema = "universe" if engine.dialect.name == "postgresql" else None
    inspector = inspect(engine)
    if "oem_vin" not in inspector.get_table_names(schema=schema):
        return
    columns = {column["name"] for column in inspector.get_columns("oem_vin", schema=schema)}
    needs_backfill = "is_valid" not in columns
    preparer = engine.dialect.identifier_preparer
    table = f"{preparer.quote_schema(schema)}.{preparer.quote('oem_vin')}" if schema else preparer.quote("oem_vin")
    with engine.begin() as connection:
        if needs_backfill:
            connection.execute(text(
                f"ALTER TABLE {table} ADD COLUMN is_valid BOOLEAN NOT NULL DEFAULT FALSE"
            ))
        if not needs_backfill:
            return
        if engine.dialect.name == "postgresql":
            connection.execute(text(f"""
                WITH ccc_pairs AS (
                    SELECT DISTINCT
                        lower(regexp_replace(btrim(oem), '\\s+', ' ', 'g')) AS oem_key,
                        lower(regexp_replace(btrim(vin), '\\s+', ' ', 'g')) AS vin_key
                    FROM universe.ccc_market_data
                ), valid_fitments AS (
                    SELECT ov.id_oem, ov.id_vin
                    FROM {table} AS ov
                    JOIN universe.oem AS o ON o.id = ov.id_oem
                    JOIN universe.vin AS v ON v.id = ov.id_vin
                    JOIN ccc_pairs AS c
                      ON c.oem_key = lower(regexp_replace(btrim(o.oem), '\\s+', ' ', 'g'))
                     AND c.vin_key = lower(regexp_replace(btrim(v.vin), '\\s+', ' ', 'g'))
                )
                UPDATE {table} AS ov
                SET is_valid = TRUE
                FROM valid_fitments AS vf
                WHERE ov.id_oem = vf.id_oem AND ov.id_vin = vf.id_vin
            """))
        else:
            ccc_pairs = {
                (normalized_key(oem), normalized_key(vin))
                for oem, vin in connection.execute(select(CccMarketRecord.oem, CccMarketRecord.vin)).all()
            }
            links = connection.execute(
                select(OEM_VIN.c.id_oem, OEM_VIN.c.id_vin, Oem.oem, Vin.vin)
                .join(Oem, Oem.id == OEM_VIN.c.id_oem)
                .join(Vin, Vin.id == OEM_VIN.c.id_vin)
            ).all()
            for id_oem, id_vin, oem, vin in links:
                connection.execute(
                    update(OEM_VIN).where(
                        OEM_VIN.c.id_oem == id_oem,
                        OEM_VIN.c.id_vin == id_vin,
                    ).values(is_valid=(normalized_key(oem), normalized_key(vin)) in ccc_pairs)
                )


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