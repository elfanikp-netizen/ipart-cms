from pathlib import Path

path = Path(r"C:\ELFANI\portal-apps\universe-site\frontend\src\pages\CccMarketPage.tsx")
text = path.read_text(encoding="utf-8-sig")
text = text.replace('<th>PREVIOUS PRICE</th>', '<th>GAP PREVIOUS PRICE</th>')
text = text.replace('{row.previous_price ? formatPrice(row.previous_price) : "â€”"}', '{row.gap_previous_price ? formatPrice(row.gap_previous_price) : "—"}')
text = text.replace('{row.previous_price ? formatPrice(row.previous_price) : "—"}', '{row.gap_previous_price ? formatPrice(row.gap_previous_price) : "—"}')
path.write_text(text, encoding="utf-8")
print("gap UI updated")
