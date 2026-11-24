import sys
import asyncio
from types import SimpleNamespace
sys.path.insert(0, r"C:\ELFANI\portal-apps\universe-site\backend")

from app.db import SessionLocal
from app.routers.ccc_market import export_ccc_lowest_price_summary

with SessionLocal() as db:
    response = export_ccc_lowest_price_summary("iPart Automotive Inc.", None, None, db, SimpleNamespace(id=1))
    body = b"".join(asyncio.run(response.body_iterator) if False else [])
    print(response.media_type)
    print(response.headers.get("content-disposition"))
