import sys
sys.path.insert(0, r"C:\ELFANI\portal-apps\universe-site\backend")

from app.db import engine
from sqlalchemy import text

with engine.connect() as connection:
    rows = connection.execute(text("""
        SELECT crawl_date,
               COUNT(*) AS rows,
               COUNT(*) FILTER (WHERE description ILIKE 'A/M%') AS stored_am,
               COUNT(*) FILTER (WHERE market_data ->> 'description_type' ILIKE 'A/M%') AS type_am
        FROM universe.ccc_market_data
        WHERE CAST(crawl_date AS date) = CAST(:day AS date)
        GROUP BY crawl_date
        ORDER BY crawl_date
    """), {"day": "2026-11-19"}).all()
    print(rows)
