import sys
sys.path.insert(0, r"C:\ELFANI\portal-apps\universe-site\backend")

from datetime import date
from app.db import SessionLocal
from app.routers.ccc_market import ccc_lowest_price_summary

with SessionLocal() as db:
    summary = ccc_lowest_price_summary(from_date=date(2026,11,19), to_date=date(2026,11,19), db=db)
    for vendor in summary["vendors"]:
        if vendor["lost_oem_count"]:
            print(vendor["vendor"], "won", vendor["won_oem_count"], "lost", vendor["lost_oem_count"])
