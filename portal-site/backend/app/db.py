from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

settings.data_dir.mkdir(parents=True, exist_ok=True)
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def set_connection_options(dbapi_conn, _):
    if engine.dialect.name == "sqlite":
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
    elif engine.dialect.name == "postgresql":
        app_schema = engine.dialect.identifier_preparer.quote_schema(settings.database_schema)
        identity_schema = engine.dialect.identifier_preparer.quote_schema("global")
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET search_path TO {app_schema}, {identity_schema}, public")
        cursor.close()
        dbapi_conn.commit()


def ensure_database_schema() -> None:
    if engine.dialect.name == "postgresql":
        app_schema = engine.dialect.identifier_preparer.quote_schema(settings.database_schema)
        identity_schema = engine.dialect.identifier_preparer.quote_schema("global")
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {app_schema}"))
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {identity_schema}"))
            connection.execute(text(f"SET search_path TO {app_schema}, {identity_schema}, public"))


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()