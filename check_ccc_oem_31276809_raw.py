import sys
sys.path.insert(0, r"C:\ELFANI\portal-apps\universe-site\backend")

from app.db import engine
from sqlalchemy import text

with engine.connect() as c:
    rows = c.execute(text("""
        SELECT crawl_date, oem, vin, description, vendor,
               market_data ->> 'description_type' AS description_type,
               market_data ->> 'description' AS market_description,
               market_data ->> 'ext-price' AS ext_price,
               market_data ->> 'total' AS total
        FROM universe.ccc_market_data
        WHERE oem = :oem
          AND crawl_date >= CAST(:day AS timestamp) - INTERVAL '1 day'
          AND crawl_date < CAST(:day AS timestamp) + INTERVAL '1 day'
        ORDER BY crawl_date DESC, description_type, vendor
    """), {"oem":"31276809", "day":"2026-11-19"}).mappings().all()
    for row in rows:
        print(dict(row))
