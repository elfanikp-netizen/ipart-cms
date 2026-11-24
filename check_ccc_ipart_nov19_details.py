import sys
sys.path.insert(0, r"C:\ELFANI\portal-apps\universe-site\backend")

from datetime import date
from app.db import SessionLocal
from app.routers.ccc_market import ccc_lowest_price_details

with SessionLocal() as db:
    for description in ("A/M: CAPA", "A/M", "RECOND", "OPT OEM"):
        won = ccc_lowest_price_details("iPart Automotive Inc.", description, "won", "oem", date(2026,11,19), date(2026,11,19), db)
        lost = ccc_lowest_price_details("iPart Automotive Inc.", description, "lost", "oem", date(2026,11,19), date(2026,11,19), db)
        print(description, "won", len(won), "lost", len(lost))
