import sys
sys.path.insert(0, r"C:\ELFANI\portal-apps\universe-site\backend")

from datetime import date
from app.db import SessionLocal
from app.routers.ccc_market import lowest_price_rows

OEM = "33150TZ3A61"
with SessionLocal() as db:
    rows = lowest_price_rows(db, date(2026, 11, 19), date(2026, 11, 19))
    matching = [row for row in rows if row["oem"].casefold() == OEM.casefold()]
    print("matching", len(matching))
    for row in sorted(matching, key=lambda r: (r["crawl_date"], r["description"], r["vendor"])):
        print(row)
