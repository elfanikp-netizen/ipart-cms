import sys
sys.path.insert(0, r"C:\ELFANI\portal-apps\universe-site\backend")

from datetime import date
from app.db import SessionLocal
from app.routers.ccc_market import ccc_lowest_price_summary

with SessionLocal() as db:
    summary = ccc_lowest_price_summary(from_date=date(2026, 11, 19), to_date=date(2026, 11, 19), db=db)
    print("totals", summary["vendor_count"], summary["oem_count"], summary["lowest_count"], summary["lost_count"])
    for vendor in summary["vendors"]:
        if vendor["vendor"].casefold() == "ipart automotive inc.":
            print("vendor", vendor["won_oem_count"], vendor["lost_oem_count"], vendor["lowest_count"], vendor["lost_count"])
            for item in vendor["descriptions"]:
                if item["won_oem_count"] or item["lost_oem_count"]:
                    print(item)
