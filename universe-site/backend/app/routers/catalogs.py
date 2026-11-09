import math
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from sqlalchemy import false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..auth import PortalUser, get_current_user, get_db
from ..audit import log_activity
from ..models import OEM_INTERCHANGE, OEM_PARTSLINK, Interchange, Oem, Partslink, Vin
from .master_data import (
    apply_column_filters,
    apply_column_sort,
    get_cell,
    normalize_text,
    normalize_vin,
    normalized_key,
    normalize_excel_header,
    resolve_vehicle,
    validate_year,
)

router = APIRouter(prefix="/api/universe", tags=["Parts catalogs"])
PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


class CatalogSpec:
    def __init__(self, model: type[Partslink] | type[Interchange], value_field: str, label: str):
        self.model = model
        self.value_field = value_field
        self.label = label


SPECS = {
    "partslinks": CatalogSpec(Partslink, "partslink", "Partslink"),
    "interchanges": CatalogSpec(Interchange, "interchange", "Interchange"),
}


def get_spec(kind: str) -> CatalogSpec:
    return SPECS[kind]


def open_workbook(file: UploadFile):
    suffix = (file.filename or "").lower().rsplit(".", 1)[-1]
    if suffix not in {"xlsx", "xlsm"}:
        raise HTTPException(400, "Upload an Excel workbook (.xlsx or .xlsm)")
    try:
        workbook = load_workbook(BytesIO(file.file.read()), read_only=True, data_only=True)
    except Exception as error:
        raise HTTPException(400, "Could not read the uploaded workbook") from error
    rows = workbook.active.iter_rows(values_only=True)
    headers = [normalize_excel_header(value) for value in next(rows, ())]
    return workbook, rows, {header: index for index, header in enumerate(headers) if header}


def excel_response(workbook: Workbook, filename: str):
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def catalog_query(spec: CatalogSpec, search: str):
    model = spec.model
    value_column = getattr(model, spec.value_field)
    stmt = select(model)
    if search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(
            value_column.ilike(pattern),
            model.description.ilike(pattern),
            model.oems.any(Oem.oem.ilike(pattern)),
        ))
    return stmt


def catalog_out(item: Partslink | Interchange, spec: CatalogSpec) -> dict[str, Any]:
    return {
        "id": item.id,
        spec.value_field: getattr(item, spec.value_field),
        "description": item.description,
        "notes": item.notes,
        "oems": sorted({oem.oem for oem in item.oems}, key=str.casefold),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def list_catalog(kind: str, page: int, page_size: int, search: str, filters: str,
                 sort_by: str, sort_dir: str, db: Session):
    spec = get_spec(kind)
    stmt = catalog_query(spec, search)
    model = spec.model
    value_column = getattr(model, spec.value_field)
    columns = {
        spec.value_field: value_column,
        "description": model.description,
        "oems": value_column,
        "updated_at": model.updated_at,
    }
    secondary = model.oems.property.secondary
    columns["oems"] = select(func.min(Oem.oem_key)).select_from(Oem).join(
        secondary, secondary.c.id_oem == Oem.id
    ).where(secondary.c[f"id_{spec.value_field}"] == model.id).correlate(model).scalar_subquery()
    empty_conditions = {"oems": ~model.oems.any()}
    value_conditions = {"oems": lambda value: model.oems.any(Oem.oem.ilike(f"%{value}%"))}
    stmt = apply_column_filters(stmt, filters, columns, empty_conditions, value_conditions)
    stmt = apply_column_sort(
        stmt, sort_by, sort_dir, columns, (model.updated_at.desc(), model.id.desc())
    )
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(
        stmt.options(selectinload(spec.model.oems))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [catalog_out(item, spec) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": math.ceil(total / page_size) if total else 0,
    }


def list_catalog_pairs(page: int, page_size: int, search: str, filters: str,
                       sort_by: str, sort_dir: str, db: Session):
    grouped = select(
        Partslink.id.label("id_partslink"),
        Partslink.partslink,
        Interchange.id.label("id_interchange"),
        Interchange.interchange,
        func.count(func.distinct(Oem.id)).label("distinct_oem_count"),
        func.max(Oem.updated_at).label("latest_updated_at"),
    ).select_from(Partslink).join(
        OEM_PARTSLINK, OEM_PARTSLINK.c.id_partslink == Partslink.id
    ).join(
        Oem, Oem.id == OEM_PARTSLINK.c.id_oem
    ).join(
        OEM_INTERCHANGE, OEM_INTERCHANGE.c.id_oem == Oem.id
    ).join(
        Interchange, Interchange.id == OEM_INTERCHANGE.c.id_interchange
    )
    if search.strip():
        pattern = f"%{search.strip()}%"
        grouped = grouped.where(or_(Partslink.partslink.ilike(pattern), Interchange.interchange.ilike(pattern)))
    grouped = grouped.group_by(Partslink.id, Partslink.partslink, Interchange.id, Interchange.interchange)
    pairs = grouped.subquery()
    stmt = select(
        pairs.c.id_partslink,
        pairs.c.partslink,
        pairs.c.id_interchange,
        pairs.c.interchange,
        pairs.c.distinct_oem_count,
    )
    columns = {
        "partslink": pairs.c.partslink,
        "interchange": pairs.c.interchange,
        "distinct_oem_count": pairs.c.distinct_oem_count,
    }
    stmt = apply_column_filters(
        stmt, filters, columns,
        empty_conditions={name: false() for name in columns},
    )
    stmt = apply_column_sort(
        stmt,
        sort_by,
        sort_dir,
        columns,
        (pairs.c.latest_updated_at.desc(), pairs.c.partslink, pairs.c.interchange),
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).mappings().all()
    return {
        "items": [dict(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": math.ceil(total / page_size) if total else 0,
    }


def export_catalog_pairs(search: str, filters: str, sort_by: str, sort_dir: str,
                         db: Session, user: PortalUser):
    grouped = select(
        Partslink.id.label("id_partslink"),
        Partslink.partslink,
        Interchange.id.label("id_interchange"),
        Interchange.interchange,
        func.count(func.distinct(Oem.id)).label("distinct_oem_count"),
        func.max(Oem.updated_at).label("latest_updated_at"),
    ).select_from(Partslink).join(
        OEM_PARTSLINK, OEM_PARTSLINK.c.id_partslink == Partslink.id
    ).join(
        Oem, Oem.id == OEM_PARTSLINK.c.id_oem
    ).join(
        OEM_INTERCHANGE, OEM_INTERCHANGE.c.id_oem == Oem.id
    ).join(
        Interchange, Interchange.id == OEM_INTERCHANGE.c.id_interchange
    )
    if search.strip():
        pattern = f"%{search.strip()}%"
        grouped = grouped.where(or_(Partslink.partslink.ilike(pattern), Interchange.interchange.ilike(pattern)))
    pairs = grouped.group_by(Partslink.id, Partslink.partslink, Interchange.id, Interchange.interchange).subquery()
    columns = {
        "partslink": pairs.c.partslink,
        "interchange": pairs.c.interchange,
        "distinct_oem_count": pairs.c.distinct_oem_count,
    }
    stmt = apply_column_filters(select(pairs), filters, columns,
                                empty_conditions={name: false() for name in columns})
    stmt = apply_column_sort(
        stmt,
        sort_by,
        sort_dir,
        columns,
        (pairs.c.latest_updated_at.desc(), pairs.c.partslink, pairs.c.interchange),
    )
    rows = db.execute(stmt).mappings().all()
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Partslink Interchange")
    sheet.append(["PARTSLINK", "INTERCHANGE", "SHARED OEM PARTS"])
    for row in rows:
        sheet.append([row["partslink"], row["interchange"], row["distinct_oem_count"]])
    log_activity(db, user, "export_partslink_interchange",
                 f"exported {len(rows)} filtered Partslink/Interchange pairs")
    return excel_response(workbook, "partslink-interchange.xlsx")


def import_catalog(kind: str, file: UploadFile, db: Session, user: PortalUser):
    spec = get_spec(kind)
    workbook, rows, indexes = open_workbook(file)
    primary_field = "partslink"
    missing = [primary_field.upper()] if primary_field not in indexes else []
    if missing:
        workbook.close()
        raise HTTPException(400, f"Missing required Excel columns: {', '.join(missing)}")
    fitment_columns = ("year", "make", "model", "vin")
    supplied_fitment_columns = [column in indexes for column in fitment_columns]
    if any(supplied_fitment_columns) and not all(supplied_fitment_columns):
        workbook.close()
        raise HTTPException(400, "Provide all four fitment columns: Year, Make, Model, and VIN")

    result = {"catalogs_created": 0, "oems_created": 0, "links_created": 0,
              "vehicles_created": 0, "vins_created": 0, "fitments_created": 0,
              "updated": 0, "skipped": 0, "errors": []}
    def value_at(row, field: str, slot: int | None = None):
        column = field if slot is None else f"{field} {slot}"
        index = indexes.get(normalize_excel_header(column))
        return get_cell(row, index) if index is not None else None

    def resolve_catalog(catalog_spec: CatalogSpec, raw_value: object, description: str):
        value = normalize_text(raw_value, catalog_spec.label)
        model = catalog_spec.model
        key = normalized_key(value)
        key_column = getattr(model, f"{catalog_spec.value_field}_key")
        item = db.scalar(select(model).where(key_column == key))
        if item is None:
            item = model(**{
                catalog_spec.value_field: value,
                f"{catalog_spec.value_field}_key": key,
                "description": description,
                "created_by": user.id,
                "updated_by": user.id,
            })
            db.add(item)
            db.flush()
            result["catalogs_created"] += 1
        elif description and item.description != description:
            item.description = description
            item.updated_by = user.id
            result["updated"] += 1
        return item

    def resolve_oem(raw_value: object, description: str):
        number = normalize_text(raw_value, "OEM")
        key = normalized_key(number)
        item = db.scalar(select(Oem).where(Oem.oem_key == key))
        if item is None:
            item = Oem(oem=number, oem_key=key, description=description,
                       created_by=user.id, updated_by=user.id)
            db.add(item)
            db.flush()
            result["oems_created"] += 1
        elif description and item.description != description:
            item.description = description
            item.updated_by = user.id
            result["updated"] += 1
        return item

    def ensure_link(catalog_item: Partslink | Interchange, oem_item: Oem):
        if oem_item not in catalog_item.oems:
            catalog_item.oems.append(oem_item)
            result["links_created"] += 1
        else:
            result["skipped"] += 1

    def ensure_vin_fitment(oem_item: Oem, vin_item: Vin):
        if vin_item not in oem_item.vins:
            oem_item.vins.append(vin_item)
            result["fitments_created"] += 1

    try:
        for row_number, row in enumerate(rows, start=2):
            try:
                with db.begin_nested():
                    partsl_value = normalize_text(value_at(row, "partslink"), "Partslink")
                    description = " ".join(str(get_cell(row, indexes.get("description", -1)) if "description" in indexes else "").strip().split())
                    partslink = resolve_catalog(SPECS["partslinks"], partsl_value, description)
                    vin_item = None
                    if all(supplied_fitment_columns):
                        year = validate_year(get_cell(row, indexes["year"]))
                        make = normalize_text(get_cell(row, indexes["make"]), "Make")
                        vehicle_model = normalize_text(get_cell(row, indexes["model"]), "Model")
                        vin_number = normalize_vin(get_cell(row, indexes["vin"]))
                        vehicle, vehicle_created, vehicle_updated = resolve_vehicle(
                            db, year, make, vehicle_model, user.id
                        )
                        result["vehicles_created"] += int(vehicle_created)
                        result["updated"] += int(vehicle_updated)
                        vin_item = db.scalar(select(Vin).where(
                            Vin.id_vehicle == vehicle.id,
                            Vin.vin_key == vin_number,
                        ))
                        if vin_item is None:
                            vin_item = Vin(
                                id_vehicle=vehicle.id,
                                vin=vin_number,
                                vin_key=vin_number,
                                created_by=user.id,
                                updated_by=user.id,
                            )
                            db.add(vin_item)
                            db.flush()
                            result["vins_created"] += 1

                    single_oem_value = value_at(row, "oem")
                    if single_oem_value is not None and str(single_oem_value).strip():
                        oem = resolve_oem(single_oem_value, description)
                        ensure_link(partslink, oem)
                        if kind == "interchanges":
                            for slot in range(1, 6):
                                interchange_value = value_at(row, "interchange", slot)
                                if interchange_value is not None and str(interchange_value).strip():
                                    interchange = resolve_catalog(
                                        SPECS["interchanges"], interchange_value, description
                                    )
                                    ensure_link(interchange, oem)
                        if vin_item is not None:
                            ensure_vin_fitment(oem, vin_item)

                    if kind == "partslinks":
                        for slot in range(1, 6):
                            interchange_value = value_at(row, "interchange", slot)
                            oem_value = value_at(row, "oem", slot)
                            if interchange_value is not None and str(interchange_value).strip():
                                interchange = resolve_catalog(SPECS["interchanges"], interchange_value, description)
                                if oem_value is not None and str(oem_value).strip():
                                    oem = resolve_oem(oem_value, description)
                                    ensure_link(partslink, oem)
                                    ensure_link(interchange, oem)
                                    if vin_item is not None:
                                        ensure_vin_fitment(oem, vin_item)
                            elif oem_value is not None and str(oem_value).strip():
                                oem = resolve_oem(oem_value, description)
                                ensure_link(partslink, oem)
                                if vin_item is not None:
                                    ensure_vin_fitment(oem, vin_item)
                    else:
                        for slot in range(1, 6):
                            interchange_value = value_at(row, "interchange", slot)
                            oem_value = value_at(row, "oem", slot)
                            if interchange_value is None or not str(interchange_value).strip():
                                continue
                            interchange = resolve_catalog(SPECS["interchanges"], interchange_value, description)
                            if oem_value is not None and str(oem_value).strip():
                                oem = resolve_oem(oem_value, description)
                                ensure_link(partslink, oem)
                                ensure_link(interchange, oem)
                                if vin_item is not None:
                                    ensure_vin_fitment(oem, vin_item)
            except ValueError as error:
                result["skipped"] += 1
                if len(result["errors"]) < 50:
                    result["errors"].append(f"Row {row_number}: {error}")
        db.commit()
        log_activity(db, user, f"import_{kind}",
                     f"catalogs_created={result['catalogs_created']} oems_created={result['oems_created']} "
                     f"links_created={result['links_created']} vehicles_created={result['vehicles_created']} "
                     f"vins_created={result['vins_created']} fitments_created={result['fitments_created']} "
                     f"updated={result['updated']} skipped={result['skipped']}")
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, f"Import conflicted with existing {spec.label} or OEM data") from error
    finally:
        workbook.close()
    return result


def export_catalog(kind: str, search: str, filters: str, sort_by: str, sort_dir: str,
                  db: Session, user: PortalUser):
    spec = get_spec(kind)
    model = spec.model
    stmt = catalog_query(spec, search)
    value_column = getattr(model, spec.value_field)
    secondary = model.oems.property.secondary
    columns = {
        spec.value_field: value_column,
        "description": model.description,
        "oems": select(func.min(Oem.oem_key)).select_from(Oem).join(
            secondary, secondary.c.id_oem == Oem.id
        ).where(secondary.c[f"id_{spec.value_field}"] == model.id).correlate(model).scalar_subquery(),
        "updated_at": model.updated_at,
    }
    stmt = apply_column_filters(stmt, filters, columns,
                                {"oems": ~model.oems.any()},
                                {"oems": lambda value: model.oems.any(Oem.oem.ilike(f"%{value}%"))})
    stmt = apply_column_sort(
        stmt, sort_by, sort_dir, columns, (model.updated_at.desc(), model.id.desc())
    )
    items = db.scalars(
        stmt.options(selectinload(model.oems))
    ).all()
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(spec.label)
    sheet.append([spec.label.upper(), "OEM", "Description"])
    exported = 0
    for item in items:
        if item.oems:
            for oem in sorted(item.oems, key=lambda value: value.oem_key):
                sheet.append([getattr(item, spec.value_field), oem.oem, oem.description or item.description])
                exported += 1
        else:
            sheet.append([getattr(item, spec.value_field), None, item.description])
            exported += 1
    log_activity(db, user, f"export_{kind}", f"exported {exported} {spec.label} to OEM mappings")
    return excel_response(workbook, f"{kind}.xlsx")


def export_catalog_by_oems(kind: str, file: UploadFile, db: Session, user: PortalUser):
    spec = get_spec(kind)
    workbook, rows, indexes = open_workbook(file)
    requested: list[tuple[str, str]] = []
    try:
        if "oem" not in indexes:
            raise HTTPException(400, "Missing required Excel column: OEM")
        for row_number, row in enumerate(rows, start=2):
            try:
                number = normalize_text(get_cell(row, indexes["oem"]), "OEM")
                requested.append((number, normalized_key(number)))
            except ValueError as error:
                raise HTTPException(400, f"Row {row_number}: {error}") from error
    finally:
        workbook.close()

    model = spec.model
    value_column = getattr(model, spec.value_field)
    key_column = getattr(model, f"{spec.value_field}_key")
    result_workbook = Workbook(write_only=True)
    sheet = result_workbook.create_sheet(spec.label)
    sheet.append([spec.label.upper(), "OEM", "Description"])
    exported = 0
    for uploaded_oem, oem_key in requested:
        oem = db.scalar(select(Oem).options(selectinload(Oem.partslinks), selectinload(Oem.interchanges))
                         .where(Oem.oem_key == oem_key))
        catalogs = []
        if oem is not None:
            catalogs = oem.partslinks if kind == "partslinks" else oem.interchanges
        if catalogs:
            for item in sorted(catalogs, key=lambda value: getattr(value, f"{spec.value_field}_key")):
                sheet.append([getattr(item, spec.value_field), oem.oem, oem.description or item.description])
                exported += 1
        else:
            sheet.append([None, uploaded_oem, None])
            exported += 1
    log_activity(db, user, f"export_{kind}_by_oem", f"exported {exported} mappings from an OEM list")
    return excel_response(result_workbook, f"{kind}-by-oem.xlsx")


def create_catalog(kind: str, payload: dict[str, Any], db: Session, user: PortalUser):
    spec = get_spec(kind)
    value = normalize_text(payload.get(spec.value_field), spec.label)
    key = normalized_key(value)
    model = spec.model
    key_column = getattr(model, f"{spec.value_field}_key")
    if db.scalar(select(model.id).where(key_column == key)) is not None:
        raise HTTPException(409, f"{spec.label} number already exists")
    item = model(
        **{spec.value_field: value, f"{spec.value_field}_key": key,
           "description": str(payload.get("description") or "").strip(),
           "notes": str(payload.get("notes") or "").strip(),
           "created_by": user.id, "updated_by": user.id}
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    log_activity(db, user, f"create_{kind[:-1]}", f"created {spec.label} {value}")
    return catalog_out(item, spec)


def update_catalog(kind: str, record_id: int, payload: dict[str, Any], db: Session, user: PortalUser):
    spec = get_spec(kind)
    item = db.get(spec.model, record_id)
    if item is None:
        raise HTTPException(404, f"{spec.label} record not found")
    value = normalize_text(payload.get(spec.value_field), spec.label)
    key = normalized_key(value)
    key_column = getattr(spec.model, f"{spec.value_field}_key")
    duplicate = db.scalar(select(spec.model.id).where(key_column == key, spec.model.id != record_id))
    if duplicate:
        raise HTTPException(409, f"{spec.label} number already exists")
    setattr(item, spec.value_field, value)
    setattr(item, f"{spec.value_field}_key", key)
    item.description = str(payload.get("description") or "").strip()
    item.notes = str(payload.get("notes") or "").strip()
    item.updated_by = user.id
    db.commit()
    db.refresh(item)
    log_activity(db, user, f"update_{kind[:-1]}", f"updated {spec.label} {value}")
    return catalog_out(item, spec)


def delete_catalog(kind: str, record_id: int, db: Session, user: PortalUser):
    spec = get_spec(kind)
    item = db.get(spec.model, record_id)
    if item is None:
        raise HTTPException(404, f"{spec.label} record not found")
    value = getattr(item, spec.value_field)
    db.delete(item)
    db.commit()
    log_activity(db, user, f"delete_{kind[:-1]}", f"deleted {spec.label} {value}")


@router.get("/partslinks")
def list_partslinks(page: int = Query(1, ge=1), page_size: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
                   search: str = "", filters: str = "", sort_by: str = "", sort_dir: str = "asc",
                   db: Session = Depends(get_db), _: PortalUser = Depends(get_current_user)):
    return list_catalog("partslinks", page, page_size, search, filters, sort_by, sort_dir, db)


@router.get("/interchanges")
def list_interchanges(page: int = Query(1, ge=1), page_size: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
                      search: str = "", filters: str = "", sort_by: str = "", sort_dir: str = "asc",
                      db: Session = Depends(get_db), _: PortalUser = Depends(get_current_user)):
    return list_catalog("interchanges", page, page_size, search, filters, sort_by, sort_dir, db)


@router.get("/partslink-interchange")
def get_partslink_interchange_pairs(
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    search: str = "",
    filters: str = "",
    sort_by: str = "",
    sort_dir: str = "asc",
    db: Session = Depends(get_db),
    _: PortalUser = Depends(get_current_user),
):
    return list_catalog_pairs(page, page_size, search, filters, sort_by, sort_dir, db)


@router.get("/partslink-interchange/export")
def export_partslink_interchange(
    search: str = "",
    filters: str = "",
    sort_by: str = "",
    sort_dir: str = "asc",
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    return export_catalog_pairs(search, filters, sort_by, sort_dir, db, user)


@router.get("/partslinks/export")
def export_partslinks(search: str = "", filters: str = "", sort_by: str = "", sort_dir: str = "asc",
                      db: Session = Depends(get_db), user: PortalUser = Depends(get_current_user)):
    return export_catalog("partslinks", search, filters, sort_by, sort_dir, db, user)


@router.get("/interchanges/export")
def export_interchanges(search: str = "", filters: str = "", sort_by: str = "", sort_dir: str = "asc",
                        db: Session = Depends(get_db), user: PortalUser = Depends(get_current_user)):
    return export_catalog("interchanges", search, filters, sort_by, sort_dir, db, user)


@router.post("/partslinks/export-by-oem")
def export_partslinks_by_oem(file: UploadFile = File(...), db: Session = Depends(get_db),
                             user: PortalUser = Depends(get_current_user)):
    return export_catalog_by_oems("partslinks", file, db, user)


@router.post("/interchanges/export-by-oem")
def export_interchanges_by_oem(file: UploadFile = File(...), db: Session = Depends(get_db),
                               user: PortalUser = Depends(get_current_user)):
    return export_catalog_by_oems("interchanges", file, db, user)


@router.post("/partslinks/import")
def import_partslinks(file: UploadFile = File(...), db: Session = Depends(get_db),
                      user: PortalUser = Depends(get_current_user)):
    return import_catalog("partslinks", file, db, user)


@router.post("/interchanges/import")
def import_interchanges(file: UploadFile = File(...), db: Session = Depends(get_db),
                        user: PortalUser = Depends(get_current_user)):
    return import_catalog("interchanges", file, db, user)


@router.post("/partslinks")
def add_partslink(payload: dict[str, Any], db: Session = Depends(get_db),
                  user: PortalUser = Depends(get_current_user)):
    return create_catalog("partslinks", payload, db, user)


@router.post("/interchanges")
def add_interchange(payload: dict[str, Any], db: Session = Depends(get_db),
                    user: PortalUser = Depends(get_current_user)):
    return create_catalog("interchanges", payload, db, user)


@router.put("/partslinks/{record_id}")
def edit_partslink(record_id: int, payload: dict[str, Any], db: Session = Depends(get_db),
                   user: PortalUser = Depends(get_current_user)):
    return update_catalog("partslinks", record_id, payload, db, user)


@router.put("/interchanges/{record_id}")
def edit_interchange(record_id: int, payload: dict[str, Any], db: Session = Depends(get_db),
                     user: PortalUser = Depends(get_current_user)):
    return update_catalog("interchanges", record_id, payload, db, user)


@router.delete("/partslinks/{record_id}", status_code=204)
def remove_partslink(record_id: int, db: Session = Depends(get_db),
                      user: PortalUser = Depends(get_current_user)):
    delete_catalog("partslinks", record_id, db, user)


@router.delete("/interchanges/{record_id}", status_code=204)
def remove_interchange(record_id: int, db: Session = Depends(get_db),
                        user: PortalUser = Depends(get_current_user)):
    delete_catalog("interchanges", record_id, db, user)
