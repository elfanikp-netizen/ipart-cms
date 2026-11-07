from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import models
from .db import (Base, ensure_database_schema, ensure_partslink_interchange_view, engine,
                 migrate_ccc_market_rows, migrate_oem_relationships,
                 migrate_user_app_access, migrate_vin_uniqueness, prepare_oem_relationship_migration)
from .routers import activity, catalogs, ccc_market, master_data, oem, parts_msrp


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_database_schema()
    prepare_oem_relationship_migration()
    Base.metadata.create_all(engine)
    migrate_oem_relationships()
    ensure_partslink_interchange_view()
    migrate_user_app_access()
    migrate_vin_uniqueness()
    migrate_ccc_market_rows()
    yield


app = FastAPI(title="Universe Master Data", lifespan=lifespan)
app.include_router(master_data.router)
app.include_router(oem.router)
app.include_router(catalogs.router)
app.include_router(ccc_market.router)
app.include_router(parts_msrp.router)
app.include_router(activity.router)


@app.get("/api/universe/health")
def health():
    return {"ok": True, "schema": "universe"}