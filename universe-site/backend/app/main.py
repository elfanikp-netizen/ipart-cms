from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import models
from .db import Base, ensure_database_schema, engine, migrate_ccc_market_rows, migrate_user_app_access, migrate_vin_uniqueness
from .routers import activity, ccc_market, master_data, oem


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_database_schema()
    Base.metadata.create_all(engine)
    migrate_user_app_access()
    migrate_vin_uniqueness()
    migrate_ccc_market_rows()
    yield


app = FastAPI(title="Universe Master Data", lifespan=lifespan)
app.include_router(master_data.router)
app.include_router(oem.router)
app.include_router(ccc_market.router)
app.include_router(activity.router)


@app.get("/api/universe/health")
def health():
    return {"ok": True, "schema": "universe"}