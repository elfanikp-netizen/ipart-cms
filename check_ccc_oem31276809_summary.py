import sys
sys.path.insert(0, r"C:\ELFANI\portal-apps\universe-site\backend")

from datetime import date
from app.db import SessionLocal
from app.routers.ccc_market import ccc_lowest_price_details, ccc_lowest_price_summary

OEM = "31276809"
with SessionLocal() as db:
    for desc in ("A/M", "A/M: CAPA"):
        won = ccc_lowest_price_details("iPart Automotive Inc.", desc, "won", "oem", date(2026,11,19), date(2026,11,19), db)
        lost = ccc_lowest_price_details("iPart Automotive Inc.", desc, "lost", "oem", date(2026,11,19), date(2026,11,19), db)
        print(desc, "ipart won", [r for r in won if r["oem"] == OEM], "ipart lost", [r for r in lost if r["oem"] == OEM])
    summary = ccc_lowest_price_summary(date(2026,11,19), date(2026,11,19), db)
    for vendor in summary["vendors"]:
        if vendor["vendor"] == "iPart Automotive Inc.":
            print("summary", vendor["won_oem_count"], vendor["lost_oem_count"])
            print(vendor["descriptions"])
