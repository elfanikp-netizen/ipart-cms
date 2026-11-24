import sys
sys.path.insert(0, r"C:\ELFANI\portal-apps\universe-site\backend")

from datetime import date
from app.db import SessionLocal
from app.routers.ccc_market import lowest_price_rows

with SessionLocal() as db:
    rows = lowest_price_rows(db, date(2026,11,19), date(2026,11,19))
    for row in rows:
        if row["oem"] == "31276809" and row["description"].casefold() in ("a/m", "a/m: capa"):
            print(row)
