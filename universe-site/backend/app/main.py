from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import models
from .db import Base, ensure_database_schema, engine
from .routers import master_data


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_database_schema()
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Universe Master Data", lifespan=lifespan)
app.include_router(master_data.router)


@app.get("/api/universe/health")
def health():
    return {"ok": True, "schema": "universe"}