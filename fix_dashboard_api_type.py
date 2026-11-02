from pathlib import Path

path = Path(r"C:\ELFANI\portal-apps\universe-site\frontend\src\api.ts")
text = path.read_text(encoding="utf-8-sig")
needle = '    lowest_price: string;\n    gap: string;\n'
replacement = '    lowest_price: string;\n    lowest_vendors: string;\n    gap: string;\n'
start = text.index("  details: {")
end = text.index("  }[];\n  details_total", start)
block = text[start:end]
if needle in block:
    block = block.replace(needle, replacement, 1)
    text = text[:start] + block + text[end:]
path.write_text(text, encoding="utf-8")
print("dashboard API type fixed")
