import json

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

settings.data_dir.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    if engine.dialect.name == "sqlite":
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
    elif engine.dialect.name == "postgresql":
        schema = engine.dialect.identifier_preparer.quote_schema(settings.database_schema)
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET search_path TO {schema}, public")
        cursor.close()
        dbapi_conn.commit()


def ensure_database_schema() -> None:
    if engine.dialect.name == "postgresql":
        schema = engine.dialect.identifier_preparer.quote_schema(settings.database_schema)
        identity_schema = engine.dialect.identifier_preparer.quote_schema("global")
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {identity_schema}"))
            connection.execute(text(f"SET search_path TO {schema}, {identity_schema}, public"))


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
