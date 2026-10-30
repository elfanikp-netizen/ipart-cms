import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import PortalUser, get_current_user, get_db
from ..audit import log_activity
from ..models import CccMarketRecord
from ..schemas import CccMarketPageOut, CccMarketRecordOut
from .master_data import excel_indexes, get_cell, open_excel

router = APIRouter(prefix="/api/universe/market/ccc", tags=["CCC Market data"])


def parse_crawl_date(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        text = str(value or "").strip()
        if not text:
            raise ValueError("date_time is required")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
            for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    parsed = datetime.strptime(text, date_format)
                    break
                except ValueError:
                    continue
            if parsed is None:
                raise ValueError("date_time must be a valid date or timestamp")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_market_data(value: Any) -> dict | list:
    if isinstance(value, (dict, list)):
        decoded = value
    else:
        text = str(value or "").strip()
        if not text:
            return []
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError("market_data must contain valid JSON") from error
    if not isinstance(decoded, (dict, list)):
        raise ValueError("market_data JSON must be an object or array")
    return decoded


def market_field(data: dict | list, field: str) -> str:
    values = data if isinstance(data, list) else [data]
    found = []
    for item in values:
        if not isinstance(item, dict):
            continue
        value = next((item[key] for key in item if key.casefold() == field), None)
        if value is not None and str(value).strip():
            rendered = str(value).strip()
            if rendered not in found:
                found.append(rendered)
    return ", ".join(found)


def market_entries(data: dict | list) -> list[dict]:
    entries = [data] if isinstance(data, dict) else data
    if any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("Every market_data array entry must be a JSON object")
    return entries


def numeric_price(value: Any) -> Decimal | None:
    if value is None:
        return None
    rendered = str(value).strip().replace("$", "").replace(",", "")
    if not rendered:
        return None
    try:
        return Decimal(rendered)
    except InvalidOperation:
        return None


def filtered_ccc_records(db: Session, oem: str, vin: str, description: str, vendor: str, search: str):
    stmt = select(CccMarketRecord)
    if oem.strip():
        stmt = stmt.where(CccMarketRecord.oem == oem.strip())
    if vin.strip():
        stmt = stmt.where(CccMarketRecord.vin == vin.strip())
    if description.strip():
        stmt = stmt.where(CccMarketRecord.description.ilike(f"%{description.strip()}%"))
    if vendor.strip():
        stmt = stmt.where(CccMarketRecord.vendor.ilike(f"%{vendor.strip()}%"))
    if search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(
            CccMarketRecord.oem.ilike(pattern),
            CccMarketRecord.vin.ilike(pattern),
            CccMarketRecord.description.ilike(pattern),
            CccMarketRecord.vendor.ilike(pattern),
            cast(CccMarketRecord.market_data, String).ilike(pattern),
        ))
    return stmt


@router.get("/filters")
def ccc_market_filters(db: Session = Depends(get_db), _: PortalUser = Depends(get_current_user)):
    rows = db.execute(select(
        CccMarketRecord.oem,
        CccMarketRecord.vin,
        CccMarketRecord.description,
        CccMarketRecord.vendor,
    ).distinct()).all()
    return {
        "oems": sorted({row.oem for row in rows if row.oem}),
        "vins": sorted({row.vin for row in rows if row.vin}),
        "descriptions": sorted({row.description for row in rows if row.description}),
        "vendors": sorted({row.vendor for row in rows if row.vendor}),
    }


@router.get("/offers")
def get_ccc_market_offers(
    oem: str = Query(..., min_length=1),
    vin: str = Query(..., min_length=1),
    crawl_date: datetime = Query(...),
    db: Session = Depends(get_db),
    _: PortalUser = Depends(get_current_user),
):
    rows = db.scalars(select(CccMarketRecord).where(
        CccMarketRecord.oem == oem,
        CccMarketRecord.vin == vin,
        CccMarketRecord.crawl_date == crawl_date,
    ).order_by(CccMarketRecord.market_index)).all()
    return [
        {"market_index": row.market_index, "market_data": row.market_data}
        for row in rows
        if row.market_data
    ]


@router.get("", response_model=CccMarketPageOut)
def list_ccc_market_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    oem: str = "",
    vin: str = "",
    description: str = "",
    vendor: str = "",
    search: str = "",
    db: Session = Depends(get_db),
    _: PortalUser = Depends(get_current_user),
):
    stmt = filtered_ccc_records(db, oem, vin, description, vendor, search)
    groups = stmt.with_only_columns(
        CccMarketRecord.oem,
        CccMarketRecord.vin,
        CccMarketRecord.crawl_date,
    ).distinct().order_by(None).subquery()
    total = db.scalar(select(func.count()).select_from(groups)) or 0
    items = db.execute(select(groups).order_by(
        groups.c.crawl_date.desc(),
        groups.c.oem,
        groups.c.vin,
    ).offset((page - 1) * page_size).limit(page_size)).mappings().all()
    return {
        "items": [dict(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/export")
def export_ccc_market_records(
    oem: str = "",
    vin: str = "",
    description: str = "",
    vendor: str = "",
    search: str = "",
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    stmt = filtered_ccc_records(db, oem, vin, description, vendor, search)
    groups = stmt.with_only_columns(
        CccMarketRecord.oem,
        CccMarketRecord.vin,
        CccMarketRecord.crawl_date,
        func.count(CccMarketRecord.id).label("offer_count"),
    ).group_by(
        CccMarketRecord.oem,
        CccMarketRecord.vin,
        CccMarketRecord.crawl_date,
    ).order_by(
        CccMarketRecord.crawl_date.desc(),
        CccMarketRecord.oem,
        CccMarketRecord.vin,
    )
    rows = db.execute(groups).all()
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("CCC Crawls")
    sheet.append(["OEM", "VIN", "Crawl Date", "Offer Count"])
    for row in rows:
        crawl_date = row.crawl_date.replace(tzinfo=None) if row.crawl_date.tzinfo else row.crawl_date
        sheet.append([row.oem, row.vin, crawl_date, row.offer_count])
    log_activity(db, user, "export_ccc_crawls", f"exported {len(rows)} filtered CCC crawls")
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="ccc-crawls.xlsx"'},
    )


def lowest_price_rows(db: Session, from_date: date | None, to_date: date | None) -> list[dict[str, Any]]:
    stmt = select(
        CccMarketRecord.oem,
        CccMarketRecord.vin,
        CccMarketRecord.crawl_date,
        CccMarketRecord.market_data,
    )
    if from_date is not None:
        stmt = stmt.where(CccMarketRecord.crawl_date >= datetime.combine(from_date, time.min, timezone.utc))
    if to_date is not None:
        stmt = stmt.where(CccMarketRecord.crawl_date < datetime.combine(to_date + timedelta(days=1), time.min, timezone.utc))

    crawls: dict[tuple[str, str, datetime], list[tuple[str, str, Decimal]]] = defaultdict(list)
    for oem, vin, crawl_date, offer in db.execute(stmt):
        if not isinstance(offer, dict):
            continue
        description = str(offer.get("description") or "").strip()
        vendor = str(offer.get("vendor") or "").strip()
        price = numeric_price(offer.get("ext-price"))
        if description and vendor and price is not None:
            crawls[(oem, vin, crawl_date)].append((description, vendor, price))

    result: list[dict[str, Any]] = []
    for crawl_key, offers in crawls.items():
        by_description: dict[str, list[tuple[str, str, Decimal]]] = defaultdict(list)
        for offer in offers:
            by_description[offer[0].casefold()].append(offer)
        for description_key, description_offers in by_description.items():
            lowest = min(offer[2] for offer in description_offers)
            description_label = description_offers[0][0]
            vendor_prices: dict[str, Decimal] = {}
            for _, vendor, price in description_offers:
                vendor_prices[vendor] = min(vendor_prices.get(vendor, price), price)
            second_lowest = min((price for price in vendor_prices.values() if price > lowest), default=None)
            lowest_vendors = sorted(vendor for vendor, price in vendor_prices.items() if price == lowest)
            second_lowest_vendors = sorted(
                vendor for vendor, price in vendor_prices.items() if second_lowest is not None and price == second_lowest
            )
            for vendor, price in vendor_prices.items():
                result.append({
                    "oem": crawl_key[0],
                    "vin": crawl_key[1],
                    "crawl_date": crawl_key[2],
                    "vendor": vendor,
                    "description": description_label,
                    "price": price,
                    "lowest_price": lowest,
                    "lowest_vendors": ", ".join(lowest_vendors),
                    "second_lowest_price": second_lowest,
                    "second_lowest_vendors": ", ".join(second_lowest_vendors),
                    "outcome": "won" if price == lowest else "lost",
                })
    return result


@router.get("/lowest-price")
def ccc_lowest_price_summary(
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    _: PortalUser = Depends(get_current_user),
):
    rows = lowest_price_rows(db, from_date, to_date)
    vendor_descriptions: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    vendor_oems: dict[str, set[str]] = defaultdict(set)
    vendor_won_oems: dict[str, set[str]] = defaultdict(set)
    vendor_lost_oems: dict[str, set[str]] = defaultdict(set)
    vendor_wins: dict[str, set[tuple[str, str, datetime]]] = defaultdict(set)
    vendor_losses: dict[str, set[tuple[str, str, datetime]]] = defaultdict(set)
    description_oems: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    description_wins: dict[tuple[str, str, str], set[tuple[str, str, datetime]]] = defaultdict(set)
    description_losses: dict[tuple[str, str, str], set[tuple[str, str, datetime]]] = defaultdict(set)

    for row in rows:
        crawl_key = (row["oem"], row["vin"], row["crawl_date"])
        vendor = row["vendor"]
        description = row["description"]
        key = (vendor, description.casefold())
        vendor_descriptions[key].append(row)
        vendor_oems[vendor].add(row["oem"])
        description_key = (vendor, description.casefold(), row["outcome"])
        description_oems[description_key].add(row["oem"])
        if row["outcome"] == "won":
            vendor_wins[vendor].add(crawl_key)
            vendor_won_oems[vendor].add(row["oem"])
            description_wins[description_key].add(crawl_key)
        else:
            vendor_losses[vendor].add(crawl_key)
            vendor_lost_oems[vendor].add(row["oem"])
            description_losses[description_key].add(crawl_key)

    vendors = []
    for vendor in sorted(
        vendor_oems,
        key=lambda item: ("ipart" not in item.casefold(), -len(vendor_wins[item]), item.casefold()),
    ):
        description_keys = {key[1] for key in vendor_descriptions if key[0] == vendor}
        descriptions = []
        for description_key in description_keys:
            won_key = (vendor, description_key, "won")
            lost_key = (vendor, description_key, "lost")
            matching_rows = vendor_descriptions[(vendor, description_key)]
            description_label = matching_rows[0]["description"]
            descriptions.append({
                "description": description_label,
                "won_oem_count": len(description_oems[won_key]),
                "won_count": len(description_wins[won_key]),
                "lost_oem_count": len(description_oems[lost_key]),
                "lost_count": len(description_losses[lost_key]),
            })
        descriptions.sort(key=lambda item: (-(item["won_count"] + item["lost_count"]), item["description"].casefold()))
        vendors.append({
            "vendor": vendor,
            "oem_count": len(vendor_oems[vendor]),
            "won_oem_count": len(vendor_won_oems[vendor]),
            "lost_oem_count": len(vendor_lost_oems[vendor]),
            "lowest_count": len(vendor_wins[vendor]),
            "lost_count": len(vendor_losses[vendor]),
            "descriptions": descriptions,
        })

    return {
        "from_date": from_date,
        "to_date": to_date,
        "vendor_count": len(vendors),
        "oem_count": len({row["oem"] for row in rows}),
        "lowest_count": len({(row["oem"], row["vin"], row["crawl_date"]) for row in rows if row["outcome"] == "won"}),
        "lost_count": len({(row["oem"], row["vin"], row["crawl_date"]) for row in rows if row["outcome"] == "lost"}),
        "vendors": vendors,
    }


@router.get("/lowest-price/details")
def ccc_lowest_price_details(
    vendor: str = Query(..., min_length=1),
    description: str = Query(..., min_length=1),
    outcome: str = Query(..., pattern="^(won|lost)$"),
    metric: str = Query("crawl", pattern="^(oem|crawl)$"),
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    _: PortalUser = Depends(get_current_user),
):
    rows = [row for row in lowest_price_rows(db, from_date, to_date)
            if row["vendor"] == vendor and row["description"].casefold() == description.casefold() and row["outcome"] == outcome]
    rows.sort(key=lambda row: (row["crawl_date"], row["oem"], row["vin"]), reverse=True)
    if metric == "oem":
        by_oem: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = by_oem.setdefault(row["oem"], {**row, "crawl_count": 0})
            item["crawl_count"] += 1
            if row["crawl_date"] > item["crawl_date"]:
                item.update(row)
                item["crawl_count"] = by_oem[row["oem"]]["crawl_count"]
        rows = sorted(by_oem.values(), key=lambda row: (row["oem"], row["vin"]))
    return [{
        **row,
        "price": str(row["price"]),
        "lowest_price": str(row["lowest_price"]),
        "second_lowest_price": str(row["second_lowest_price"]) if row["second_lowest_price"] is not None else None,
    } for row in rows]


@router.get("/lowest-price/export")
def export_ccc_lowest_price_details(
    vendor: str = Query(..., min_length=1),
    description: str = Query(..., min_length=1),
    outcome: str = Query(..., pattern="^(won|lost)$"),
    metric: str = Query("crawl", pattern="^(oem|crawl)$"),
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    rows = ccc_lowest_price_details(vendor, description, outcome, metric, from_date, to_date, db)
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Lowest Price")
    sheet.append(["OEM", "VIN", "Crawl Date", "Vendor", "Description", "Outcome", "Price", "Lowest Vendor(s)", "Lowest Price", "Second Lowest Vendor(s)", "Second Lowest Price", "Crawls per OEM"])
    for row in rows:
        crawl_date = row["crawl_date"].replace(tzinfo=None) if row["crawl_date"].tzinfo else row["crawl_date"]
        sheet.append([row["oem"], row["vin"], crawl_date, row["vendor"], row["description"], row["outcome"], row["price"], row["lowest_vendors"], row["lowest_price"], row["second_lowest_vendors"], row["second_lowest_price"], row.get("crawl_count", 1)])
    log_activity(db, user, "export_ccc_lowest_price_details", f"exported {len(rows)} CCC market detail rows")
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    filename = f"ccc-{outcome}-{metric}-details.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/import")
def import_ccc_market_records(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    workbook, rows, headers = open_excel(file)
    created = updated = skipped = 0
    errors: list[str] = []
    try:
        indexes = excel_indexes(headers, ("VIN", "OEM", "Status", "date_time", "market_data"))
        for row_number, row in enumerate(rows, start=2):
            try:
                status = str(get_cell(row, indexes["Status"]) or "").strip()
                if status.casefold() != "ok":
                    skipped += 1
                    continue
                oem = str(get_cell(row, indexes["OEM"]) or "").strip().upper()
                vin = str(get_cell(row, indexes["VIN"]) or "").strip().upper()
                if not oem or not vin:
                    raise ValueError("OEM and VIN are required")
                crawl_date = parse_crawl_date(get_cell(row, indexes["date_time"]))
                market_data = parse_market_data(get_cell(row, indexes["market_data"]))
                entries = market_entries(market_data)
                stored_entries = entries or [{}]
                with db.begin_nested():
                    existing = db.scalars(select(CccMarketRecord).where(
                        CccMarketRecord.oem == oem,
                        CccMarketRecord.vin == vin,
                        CccMarketRecord.crawl_date == crawl_date,
                    ).order_by(CccMarketRecord.market_index)).all()
                    old_data = [record.market_data for record in existing]
                    if old_data == stored_entries:
                        skipped += len(stored_entries)
                    else:
                        if existing:
                            for record in existing:
                                db.delete(record)
                            db.flush()
                        for market_index, offer in enumerate(stored_entries):
                            db.add(CccMarketRecord(
                                oem=oem,
                                vin=vin,
                                crawl_date=crawl_date,
                                market_index=market_index,
                                description=market_field(offer, "description"),
                                vendor=market_field(offer, "vendor"),
                                market_data=offer,
                            ))
                        db.flush()
                        if existing:
                            updated += len(stored_entries)
                        else:
                            created += len(stored_entries)
            except (ValueError, TypeError) as error:
                skipped += 1
                if len(errors) < 50:
                    errors.append(f"Row {row_number}: {error}")
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Import conflicted with an existing CCC market key") from error
    finally:
        workbook.close()
    log_activity(db, user, "import_ccc_market", f"created={created} updated={updated} skipped={skipped}")
    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}
