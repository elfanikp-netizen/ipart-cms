from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
import json
import math
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..auth import PortalUser, get_current_user, get_db
from ..audit import log_activity
from ..models import CccMarketRecord, Oem, PartsMsrp, Vin
from .ccc_market import matching_oem_price, parse_crawl_date
from .master_data import excel_indexes, get_cell, open_excel, normalized_key

router = APIRouter(prefix="/api/universe/market/parts-msrp", tags=["Parts MSRP"])
PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def parse_msrp(value: Any) -> Decimal:
    rendered = str(value or "").strip().replace("$", "").replace(",", "")
    if not rendered:
        raise ValueError("MSRP is required")
    try:
        return Decimal(rendered).quantize(Decimal("0.01"))
    except InvalidOperation as error:
        raise ValueError("MSRP must be a valid number") from error


def excel_datetime(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def history_previous_values(records: list[PartsMsrp]) -> dict[int, Decimal | None]:
    by_oem: dict[str, list[PartsMsrp]] = {}
    for record in records:
        by_oem.setdefault(normalized_key(record.oem), []).append(record)
    previous: dict[int, Decimal | None] = {}
    for snapshots in by_oem.values():
        ordered = sorted(snapshots, key=lambda item: (item.crawl_date, item.id or 0), reverse=True)
        for index, record in enumerate(ordered):
            previous[record.id] = ordered[index + 1].msrp if index + 1 < len(ordered) else None
    return previous


def ccc_price_history(records: list[CccMarketRecord]) -> dict[str, tuple[Decimal | None, Decimal | None]]:
    prices_by_oem_date: dict[str, dict[datetime, Decimal]] = {}
    for record in records:
        try:
            price = matching_oem_price(record.market_data)
        except ValueError:
            continue
        if price is None:
            continue
        key = normalized_key(record.oem)
        date_prices = prices_by_oem_date.setdefault(key, {})
        date_prices[record.crawl_date] = min(date_prices.get(record.crawl_date, price), price)

    result = {}
    for key, date_prices in prices_by_oem_date.items():
        ordered = sorted(date_prices.items(), key=lambda item: item[0], reverse=True)
        result[key] = (ordered[0][1], ordered[1][1] if len(ordered) > 1 else None)
    return result


def fitments_by_oem(db: Session, oem_values: set[str]) -> dict[str, list[str]]:
    keys = {normalized_key(value) for value in oem_values}
    if not keys:
        return {}
    oems = db.scalars(
        select(Oem)
        .options(selectinload(Oem.vins).joinedload(Vin.vehicle))
        .where(Oem.oem_key.in_(keys))
    ).all()
    result: dict[str, list[str]] = {}
    for oem in oems:
        fitments = sorted({
            f"{vin.vehicle.year} {vin.vehicle.make} {vin.vehicle.model} · {vin.vin}"
            for vin in oem.vins
        })
        result[normalized_key(oem.oem)] = fitments
    return result


def enrich_parts_msrp_records(db: Session, records: list[PartsMsrp]) -> list[dict[str, Any]]:
    if not records:
        return []
    oem_values = {record.oem for record in records}
    normalized_oems = {normalized_key(value) for value in oem_values}
    history = db.scalars(
        select(PartsMsrp)
        .where(func.lower(PartsMsrp.oem).in_(normalized_oems))
        .order_by(PartsMsrp.crawl_date.desc(), PartsMsrp.id.desc())
    ).all()
    previous_msrp = history_previous_values(history)
    ccc_records = db.scalars(
        select(CccMarketRecord)
        .where(func.lower(CccMarketRecord.oem).in_(normalized_oems))
        .order_by(CccMarketRecord.crawl_date.desc(), CccMarketRecord.id.desc())
    ).all()
    ccc_prices = ccc_price_history(ccc_records)
    fitments = fitments_by_oem(db, oem_values)

    result = []
    for record in records:
        key = normalized_key(record.oem)
        previous = previous_msrp.get(record.id)
        ccc_current, ccc_previous = ccc_prices.get(key, (None, None))
        msrp = Decimal(record.msrp)
        result.append({
            "id": record.id,
            "oem": record.oem,
            "fitments": fitments.get(key, []),
            "msrp": str(msrp),
            "previous_msrp": str(previous) if previous is not None else None,
            "ccc_price": str(ccc_current) if ccc_current is not None else None,
            "previous_ccc_price": str(ccc_previous) if ccc_previous is not None else None,
            "gap_msrp": str(msrp - previous) if previous is not None else None,
            "gap_ccc": str(msrp - ccc_current) if ccc_current is not None else None,
            "crawl_date": record.crawl_date,
        })
    return result


def query_parts_msrp(db: Session, search: str):
    stmt = select(PartsMsrp)
    if search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(PartsMsrp.oem.ilike(pattern)))
    return stmt


PARTS_MSRP_COLUMNS = (
    "oem", "fitments", "msrp", "previous_msrp", "ccc_price",
    "previous_ccc_price", "gap_msrp", "gap_ccc", "crawl_date",
)
NUMERIC_PARTS_MSRP_COLUMNS = {
    "msrp", "previous_msrp", "ccc_price", "previous_ccc_price", "gap_msrp", "gap_ccc",
}


def filter_sort_parts_msrp(
    items: list[dict[str, Any]], filters_json: str, sort_by: str, sort_dir: str
) -> list[dict[str, Any]]:
    try:
        filters = json.loads(filters_json) if filters_json else {}
    except json.JSONDecodeError as error:
        raise HTTPException(400, "Invalid column filters") from error
    if not isinstance(filters, dict):
        raise HTTPException(400, "Column filters must be an object")

    filtered = items
    for field, options in filters.items():
        if field not in PARTS_MSRP_COLUMNS or not isinstance(options, dict):
            raise HTTPException(400, f"Unsupported column filter: {field}")
        mode = options.get("mode", "any")
        if mode not in {"any", "empty", "nonempty"}:
            raise HTTPException(400, f"Unsupported empty filter mode: {mode}")
        value = str(options.get("value", "")).strip().casefold()

        def matches(item: dict[str, Any]) -> bool:
            raw = item.get(field)
            rendered = "; ".join(raw) if isinstance(raw, list) else str(raw or "")
            empty = not rendered.strip()
            if mode == "empty" and not empty:
                return False
            if mode == "nonempty" and empty:
                return False
            return not value or value in rendered.casefold()

        filtered = [item for item in filtered if matches(item)]

    if sort_by:
        if sort_by not in PARTS_MSRP_COLUMNS:
            raise HTTPException(400, f"Unsupported sort column: {sort_by}")
        if sort_dir not in {"asc", "desc"}:
            raise HTTPException(400, "Sort direction must be asc or desc")
        reverse = sort_dir == "desc"

        def sort_value(item: dict[str, Any]):
            raw = item.get(sort_by)
            if raw is None:
                return (1, "")
            if sort_by == "fitments":
                return (0, "; ".join(raw).casefold())
            if sort_by in NUMERIC_PARTS_MSRP_COLUMNS:
                try:
                    return (0, Decimal(str(raw)))
                except InvalidOperation:
                    return (1, Decimal(0))
            if sort_by == "crawl_date":
                return (0, raw.isoformat() if isinstance(raw, datetime) else str(raw))
            return (0, str(raw).casefold())

        filtered = sorted(filtered, key=sort_value, reverse=reverse)
    else:
        filtered = sorted(
            filtered,
            key=lambda item: (item["crawl_date"], item["oem"], item["id"]),
            reverse=True,
        )
    return filtered


def parts_msrp_items(db: Session, search: str, filters: str, sort_by: str, sort_dir: str):
    records = db.scalars(query_parts_msrp(db, search)).all()
    enriched = enrich_parts_msrp_records(db, records)
    return filter_sort_parts_msrp(enriched, filters, sort_by, sort_dir)


@router.get("")
def list_parts_msrp(
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    search: str = "",
    filters: str = "",
    sort_by: str = "",
    sort_dir: str = "asc",
    db: Session = Depends(get_db),
    _: PortalUser = Depends(get_current_user),
):
    items = parts_msrp_items(db, search, filters, sort_by, sort_dir)
    total = len(items)
    return {
        "items": items[(page - 1) * page_size:page * page_size],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/export")
def export_parts_msrp(
    search: str = "",
    filters: str = "",
    sort_by: str = "",
    sort_dir: str = "asc",
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    items = parts_msrp_items(db, search, filters, sort_by, sort_dir)
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Parts MSRP")
    sheet.append([
        "OEM", "Fitments", "MSRP", "Previous MSRP", "CCC Price",
        "Previous CCC Price", "Gap MSRP", "Gap CCC", "Crawl Date",
    ])
    for item in items:
        sheet.append([
            item["oem"], "\n".join(item["fitments"]), item["msrp"],
            item["previous_msrp"], item["ccc_price"], item["previous_ccc_price"],
            item["gap_msrp"], item["gap_ccc"], excel_datetime(item["crawl_date"]),
        ])
    log_activity(db, user, "export_parts_msrp", f"exported {len(items)} Parts MSRP rows")
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="parts-msrp.xlsx"'},
    )


@router.post("/export-by-list")
def export_parts_msrp_by_list(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    workbook, rows, headers = open_excel(file)
    try:
        header_indexes = {header.casefold(): index for index, header in enumerate(headers) if header}
        oem_index = next(
            (header_indexes[alias] for alias in ("oem", "oem number") if alias in header_indexes),
            None,
        )
        if oem_index is None:
            raise HTTPException(400, "Missing required Excel column: OEM or OEM Number")
        requested = {
            normalized_key(str(get_cell(row, oem_index) or "").strip())
            for row in rows
            if str(get_cell(row, oem_index) or "").strip()
        }
    finally:
        workbook.close()

    records = db.scalars(
        select(PartsMsrp)
        .where(func.lower(PartsMsrp.oem).in_(requested))
        .order_by(PartsMsrp.crawl_date.desc(), PartsMsrp.oem, PartsMsrp.id.desc())
    ).all() if requested else []
    items = enrich_parts_msrp_records(db, records)
    output = Workbook(write_only=True)
    sheet = output.create_sheet("Parts MSRP")
    sheet.append([
        "OEM", "Fitments", "MSRP", "Previous MSRP", "CCC Price",
        "Previous CCC Price", "Gap MSRP", "Gap CCC", "Crawl Date",
    ])
    for item in items:
        sheet.append([
            item["oem"], "\n".join(item["fitments"]), item["msrp"],
            item["previous_msrp"], item["ccc_price"], item["previous_ccc_price"],
            item["gap_msrp"], item["gap_ccc"], excel_datetime(item["crawl_date"]),
        ])
    log_activity(db, user, "export_parts_msrp_by_list", f"exported {len(items)} snapshots from OEM list")
    stream = BytesIO()
    output.save(stream)
    output.close()
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="parts-msrp-by-oem.xlsx"'},
    )


@router.post("/import")
def import_parts_msrp(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    workbook, rows, headers = open_excel(file)
    created = updated = skipped = 0
    errors: list[str] = []
    try:
        indexes = excel_indexes(headers, ("msrp", "date"))
        header_indexes = {header.casefold(): index for index, header in enumerate(headers) if header}
        oem_index = next(
            (header_indexes[alias] for alias in ("oem", "oem number") if alias in header_indexes),
            None,
        )
        if oem_index is None:
            raise HTTPException(400, "Missing required Excel column: OEM or OEM Number")
        indexes["oem"] = oem_index
        for row_number, row in enumerate(rows, start=2):
            try:
                raw_oem = get_cell(row, indexes["oem"])
                raw_msrp = get_cell(row, indexes["msrp"])
                if not str(raw_oem or "").strip() or not str(raw_msrp or "").strip():
                    skipped += 1
                    continue
                oem = str(raw_oem).strip().upper()
                msrp = parse_msrp(raw_msrp)
                crawl_date = parse_crawl_date(get_cell(row, indexes["date"]))
                with db.begin_nested():
                    existing = db.scalar(select(PartsMsrp).where(
                        func.lower(PartsMsrp.oem) == normalized_key(oem),
                        PartsMsrp.crawl_date == crawl_date,
                    ))
                    if existing is None:
                        db.add(PartsMsrp(oem=oem, msrp=msrp, crawl_date=crawl_date))
                        created += 1
                    elif Decimal(existing.msrp) == msrp:
                        skipped += 1
                    else:
                        existing.msrp = msrp
                        updated += 1
            except (ValueError, TypeError) as error:
                skipped += 1
                if len(errors) < 50:
                    errors.append(f"Row {row_number}: {error}")
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Import conflicted with an existing Parts MSRP OEM/date") from error
    finally:
        workbook.close()
    log_activity(
        db,
        user,
        "import_parts_msrp",
        f"created={created} updated={updated} skipped={skipped}",
    )
    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}
