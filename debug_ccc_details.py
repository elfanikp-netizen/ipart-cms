import sys
sys.path.insert(0, r"C:\ELFANI\portal-apps\universe-site\backend")

from app.db import SessionLocal
from app.routers.ccc_market import ccc_lowest_price_summary, ccc_lowest_price_details

with SessionLocal() as db:
    summary = ccc_lowest_price_summary(from_date=None, to_date=None, db=db)
    for vendor_item in summary["vendors"]:
        for description_item in vendor_item["descriptions"]:
            if description_item["won_oem_count"] or description_item["lost_oem_count"]:
                print("TRY", vendor_item["vendor"], description_item["description"], description_item["won_oem_count"], description_item["lost_oem_count"])
                try:
                    won = ccc_lowest_price_details(vendor_item["vendor"], description_item["description"], "won", "oem", None, None, db)
                    print("WON", len(won))
                except Exception as exc:
                    print("WON_ERROR", type(exc).__name__, repr(exc))
                try:
                    lost = ccc_lowest_price_details(vendor_item["vendor"], description_item["description"], "lost", "oem", None, None, db)
                    print("LOST", len(lost))
                except Exception as exc:
                    print("LOST_ERROR", type(exc).__name__, repr(exc))
                raise SystemExit
