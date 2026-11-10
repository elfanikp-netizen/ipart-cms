import math
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from ..auth import PortalUser, get_current_user, get_db
from ..audit import log_activity
from ..models import OEM_INTERCHANGE, OEM_PARTSLINK, OEM_VIN, Interchange, Oem, Partslink, Vehicle, Vin
from ..schemas import OemCreate, OemImportOut, OemOut, OemUpdate, OemVinOut
from .master_data import (
    apply_column_filters,
    apply_column_sort,
    get_cell,
    normalize_text,
    normalize_excel_header,
    normalize_vin,
    normalized_key,
    resolve_vehicle,
    validate_year,
)

router = APIRouter(prefix="/api/universe/oems", tags=["OEM master data"])
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def row_out(item: Oem) -> OemOut:
    return OemOut(
        id=item.id,
        oem=item.oem,
        description=item.description,
        notes=item.notes,
        vins=[OemVinOut(id=vin.id, vin=vin.vin, year=vin.vehicle.year,
                        make=vin.vehicle.make, model=vin.vehicle.model)
              for vin in sorted(item.vins, key=lambda value: value.vin_key)],
        partslinks=sorted(part.partslink for part in item.partslinks),
        interchanges=sorted(group.interchange for group in item.interchanges),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def query_oems(search: str):
    stmt = select(Oem)
    if search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(
            Oem.oem.ilike(pattern),
            Oem.description.ilike(pattern),
            Oem.vins.any(Vin.vin.ilike(pattern)),
            Oem.vins.any(Vin.vehicle.has(or_(
                Vehicle.make.ilike(pattern),
                Vehicle.model.ilike(pattern),
                cast(Vehicle.year, String).ilike(pattern),
            ))),
        ))
    return stmt


def get_oem_or_404(db: Session, oem_id: int) -> Oem:
    item = db.scalar(
        select(Oem).options(
            selectinload(Oem.vins).joinedload(Vin.vehicle),
            selectinload(Oem.partslinks),
            selectinload(Oem.interchanges),
        ).where(Oem.id == oem_id)
    )
    if item is None:
        raise HTTPException(404, "OEM record not found")
    return item


def normalize_oem(value: object) -> tuple[str, str]:
    oem = normalize_text(value, "OEM")
    if len(oem) > 150:
        raise ValueError("OEM must be 150 characters or fewer")
    return oem, normalized_key(oem)


@router.post("", response_model=OemOut, status_code=201)
def create_oem(
    payload: OemCreate,
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    vin_item = db.get(Vin, payload.id_vin) if payload.id_vin is not None else None
    if payload.id_vin is not None and vin_item is None:
        raise HTTPException(404, "VIN not found")
    try:
        oem, oem_key = normalize_oem(payload.oem)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    item = db.scalar(select(Oem).where(Oem.oem_key == oem_key))
    created = item is None
    if item is None:
        item = Oem(oem=oem, oem_key=oem_key, description=payload.description.strip(),
                   notes=payload.notes.strip(), created_by=user.id, updated_by=user.id)
        db.add(item)
        db.flush()
    else:
        item.oem = oem
        item.description = payload.description.strip() or item.description
        item.notes = payload.notes.strip() or item.notes
        item.updated_by = user.id
    linked = vin_item is not None and vin_item not in item.vins
    if linked:
        item.vins.append(vin_item)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "This OEM number already exists") from error
    item = get_oem_or_404(db, item.id)
    detail = f"created OEM {item.oem}" if created else f"updated OEM {item.oem}"
    if vin_item is not None:
        detail += f" for VIN {vin_item.vin}"
    log_activity(db, user, "create_oem", detail)
    return row_out(item)


@router.put("/{oem_id}", response_model=OemOut)
def update_oem(
    oem_id: int,
    payload: OemUpdate,
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    item = get_oem_or_404(db, oem_id)
    vin_item = db.get(Vin, payload.id_vin) if payload.id_vin is not None else None
    if payload.id_vin is not None and vin_item is None:
        raise HTTPException(404, "VIN not found")
    try:
        oem, oem_key = normalize_oem(payload.oem)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    duplicate = db.scalar(select(Oem.id).where(Oem.oem_key == oem_key, Oem.id != item.id))
    if duplicate:
        raise HTTPException(409, "This OEM number already exists")
    source_vin = db.get(Vin, payload.source_id_vin) if payload.source_id_vin is not None else None
    if payload.source_id_vin is not None and source_vin is None:
        raise HTTPException(404, "Source VIN not found")
    if source_vin is not None and source_vin in item.vins and source_vin != vin_item:
        item.vins.remove(source_vin)
    linked = vin_item is not None and vin_item not in item.vins
    if linked:
        item.vins.append(vin_item)
    item.oem = oem
    item.oem_key = oem_key
    item.description = payload.description.strip()
    item.notes = payload.notes.strip()
    item.updated_by = user.id
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "This OEM number already exists") from error
    item = get_oem_or_404(db, item.id)
    log_activity(db, user, "update_oem", f"updated OEM {item.oem}")
    return row_out(item)


@router.delete("/{oem_id}", status_code=204)
def delete_oem(
    oem_id: int,
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    item = get_oem_or_404(db, oem_id)
    detail = f"deleted OEM {item.oem} and its fitment/catalog links"
    db.delete(item)
    db.commit()
    log_activity(db, user, "delete_oem", detail)
    return Response(status_code=204)


@router.delete("/{oem_id}/vins/{vin_id}", status_code=204)
def delete_oem_vin(oem_id: int, vin_id: int, db: Session = Depends(get_db),
                   user: PortalUser = Depends(get_current_user)):
    item = get_oem_or_404(db, oem_id)
    vin_item = next((value for value in item.vins if value.id == vin_id), None)
    if vin_item is None:
        raise HTTPException(404, "OEM fitment not found")
    item.vins.remove(vin_item)
    db.commit()
    log_activity(db, user, "delete_oem_fitment", f"removed OEM {item.oem} fitment for VIN {vin_item.vin}")
    return Response(status_code=204)


def workbook_rows(file: UploadFile):
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
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("")
def list_oems(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    search: str = "",
    filters: str = "",
    sort_by: str = "",
    sort_dir: str = "asc",
    db: Session = Depends(get_db),
    _: PortalUser = Depends(get_current_user),
):
    stmt = select(Oem)
    if search.strip():
        matching = query_oems(search).with_only_columns(Oem.id)
        stmt = stmt.where(Oem.id.in_(matching))
    columns = {
        "oem": Oem.oem,
        "vins": select(func.min(Vin.vin_key)).join(OEM_VIN, OEM_VIN.c.id_vin == Vin.id)
            .where(OEM_VIN.c.id_oem == Oem.id).scalar_subquery(),
        "partslinks": select(func.min(Partslink.partslink_key)).join(
            OEM_PARTSLINK, OEM_PARTSLINK.c.id_partslink == Partslink.id
        ).where(OEM_PARTSLINK.c.id_oem == Oem.id).scalar_subquery(),
        "interchanges": select(func.min(Interchange.interchange_key)).join(
            OEM_INTERCHANGE, OEM_INTERCHANGE.c.id_interchange == Interchange.id
        ).where(OEM_INTERCHANGE.c.id_oem == Oem.id).scalar_subquery(),
        "description": Oem.description,
        "updated_at": Oem.updated_at,
    }
    empty_conditions = {
        "vins": ~Oem.vins.any(),
        "partslinks": ~Oem.partslinks.any(),
        "interchanges": ~Oem.interchanges.any(),
    }
    value_conditions = {
        "vins": lambda value: Oem.vins.any(or_(
            Vin.vin.ilike(f"%{value}%"),
            Vin.vehicle.has(or_(Vehicle.make.ilike(f"%{value}%"), Vehicle.model.ilike(f"%{value}%"),
                                cast(Vehicle.year, String).ilike(f"%{value}%"))),
        )),
        "partslinks": lambda value: Oem.partslinks.any(Partslink.partslink.ilike(f"%{value}%")),
        "interchanges": lambda value: Oem.interchanges.any(Interchange.interchange.ilike(f"%{value}%")),
    }
    stmt = apply_column_filters(stmt, filters, columns, empty_conditions, value_conditions)
    stmt = apply_column_sort(stmt, sort_by, sort_dir, columns, (Oem.updated_at.desc(), Oem.id.desc()))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(
        stmt.options(
            selectinload(Oem.vins).joinedload(Vin.vehicle),
            selectinload(Oem.partslinks),
            selectinload(Oem.interchanges),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [row_out(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/export")
def export_oems(
    search: str = "",
    filters: str = "",
    sort_by: str = "",
    sort_dir: str = "asc",
    group_by_type: bool = True,
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    stmt = select(Oem)
    if search.strip():
        matching = query_oems(search).with_only_columns(Oem.id)
        stmt = stmt.where(Oem.id.in_(matching))
    columns = {
        "oem": Oem.oem,
        "vins": select(func.min(Vin.vin_key)).join(OEM_VIN, OEM_VIN.c.id_vin == Vin.id)
            .where(OEM_VIN.c.id_oem == Oem.id).scalar_subquery(),
        "partslinks": select(func.min(Partslink.partslink_key)).join(
            OEM_PARTSLINK, OEM_PARTSLINK.c.id_partslink == Partslink.id
        ).where(OEM_PARTSLINK.c.id_oem == Oem.id).scalar_subquery(),
        "interchanges": select(func.min(Interchange.interchange_key)).join(
            OEM_INTERCHANGE, OEM_INTERCHANGE.c.id_interchange == Interchange.id
        ).where(OEM_INTERCHANGE.c.id_oem == Oem.id).scalar_subquery(),
        "description": Oem.description,
        "updated_at": Oem.updated_at,
    }
    empty_conditions = {
        "vins": ~Oem.vins.any(),
        "partslinks": ~Oem.partslinks.any(),
        "interchanges": ~Oem.interchanges.any(),
    }
    value_conditions = {
        "vins": lambda value: Oem.vins.any(or_(
            Vin.vin.ilike(f"%{value}%"),
            Vin.vehicle.has(or_(Vehicle.make.ilike(f"%{value}%"), Vehicle.model.ilike(f"%{value}%"),
                                cast(Vehicle.year, String).ilike(f"%{value}%"))),
        )),
        "partslinks": lambda value: Oem.partslinks.any(Partslink.partslink.ilike(f"%{value}%")),
        "interchanges": lambda value: Oem.interchanges.any(Interchange.interchange.ilike(f"%{value}%")),
    }
    stmt = apply_column_filters(stmt, filters, columns, empty_conditions, value_conditions)
    stmt = apply_column_sort(stmt, sort_by, sort_dir, columns, (Oem.updated_at.desc(), Oem.id.desc()))
    items = db.scalars(stmt.options(selectinload(Oem.vins).joinedload(Vin.vehicle))).all()
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("OEM")
    sheet.append(["OEM", "VIN", "Year", "Make", "Model", "Description", "Notes"])
    exported = 0
    for item in items:
        vins = sorted(item.vins, key=lambda value: value.vin_key) or [None]
        if group_by_type:
            vins = vins[:1]
        for vin_item in vins:
            vehicle = vin_item.vehicle if vin_item else None
            sheet.append([item.oem, vin_item.vin if vin_item else None,
                          vehicle.year if vehicle else None, vehicle.make if vehicle else None,
                          vehicle.model if vehicle else None, item.description, item.notes])
            exported += 1
    log_activity(db, user, "export_oems", f"exported {exported} OEM rows")
    return excel_response(workbook, "oems.xlsx")


@router.post("/export-by-list")
def export_oems_by_list(
    file: UploadFile = File(...),
    list_type: str = Form("oem"),
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
    group_by_type: bool = Form(True),
):
    list_type = list_type.strip().casefold()
    if list_type not in {"oem", "partslink", "interchange"}:
        raise HTTPException(400, "List type must be OEM, Partslink, or Interchange")
    workbook, rows, indexes = workbook_rows(file)
    requested_rows: list[tuple[str, str, str | None]] = []
    list_header = next(
        (normalize_excel_header(alias) for alias in {
            "oem": ("OEM", "OEM Number"),
            "partslink": ("Partslink", "Partslink Number"),
            "interchange": ("Interchange", "Interchange Number"),
        }[list_type] if normalize_excel_header(alias) in indexes),
        normalize_excel_header(list_type),
    )
    try:
        if list_header not in indexes:
            raise HTTPException(400, f"Missing required Excel column: {list_type.title()}")
        keys: set[tuple[str, str] | tuple[str, None]] = set()
        for row_number, row in enumerate(rows, start=2):
            try:
                uploaded_number = normalize_text(get_cell(row, indexes[list_header]), list_type.title())
                number_key = normalized_key(uploaded_number)
                vin_key = normalize_vin(get_cell(row, indexes["vin"])) if "vin" in indexes and get_cell(row, indexes["vin"]) else None
                keys.add((number_key, vin_key))
                requested_rows.append((uploaded_number, number_key, vin_key))
            except ValueError as error:
                raise HTTPException(400, f"Row {row_number}: {error}") from error
    finally:
        workbook.close()

    keys_only = {number_key for number_key, _ in keys}
    if list_type == "oem":
        conditions = [Oem.oem_key.in_(keys_only)] if keys_only else []
        conditions.extend(
            Oem.vins.any(Vin.vin_key == vin_key) & (Oem.oem_key == number_key)
            for number_key, vin_key in keys if vin_key is not None
        )
        stmt = select(Oem).options(selectinload(Oem.vins).joinedload(Vin.vehicle))
        stmt = stmt.where(or_(*conditions)) if conditions else stmt.where(False)
        items = db.scalars(stmt.order_by(Oem.oem_key)).all()
        items_by_key = {item.oem_key: item for item in items}
    else:
        source_model = Partslink if list_type == "partslink" else Interchange
        source_key = f"{list_type}_key"
        source_items = db.scalars(
            select(source_model).where(getattr(source_model, source_key).in_(keys_only))
            .options(selectinload(source_model.oems).selectinload(Oem.vins).joinedload(Vin.vehicle))
        ).all() if keys_only else []
        items_by_key = {getattr(item, source_key): item for item in source_items}

    output = Workbook(write_only=True)
    sheet = output.create_sheet("OEM")
    base_headers = ["OEM", "VIN", "Year", "Make", "Model", "Description", "Notes"]
    sheet.append(base_headers if list_type == "oem" else [list_type.upper(), *base_headers])
    exported_count = 0
    seen_oem_keys: set[str] = set()
    seen_missing_keys: set[str] = set()
    for uploaded_number, number_key, vin_key in requested_rows:
        if list_type == "oem":
            item = items_by_key.get(number_key)
            matching_oems = [item] if item is not None else []
        else:
            source_item = items_by_key.get(number_key)
            matching_oems = sorted(source_item.oems, key=lambda value: value.oem_key) if source_item else []

        if not matching_oems:
            if group_by_type and number_key in seen_missing_keys:
                continue
            seen_missing_keys.add(number_key)
            row = [uploaded_number, None, None, None, None, None, None]
            sheet.append(row if list_type == "oem" else [uploaded_number, *row])
            exported_count += 1
            continue

        for item in matching_oems:
            if group_by_type and item.oem_key in seen_oem_keys:
                continue
            seen_oem_keys.add(item.oem_key)
            vins = sorted(item.vins, key=lambda value: value.vin_key)
            if vin_key is not None:
                vins = [value for value in vins if value.vin_key == vin_key]
            if group_by_type:
                vins = vins[:1]
            if vins:
                for vin_item in vins:
                    vehicle = vin_item.vehicle
                    row = [item.oem, vin_item.vin, vehicle.year, vehicle.make, vehicle.model,
                           item.description, item.notes]
                    sheet.append(row if list_type == "oem" else [uploaded_number, *row])
                    exported_count += 1
            else:
                row = [item.oem, vin_key, None, None, None, item.description, item.notes]
                sheet.append(row if list_type == "oem" else [uploaded_number, *row])
                exported_count += 1
    log_activity(db, user, "export_oems_by_list", f"exported {exported_count} OEM records from supplied {list_type} list")
    return excel_response(output, "oems-by-list.xlsx")


@router.post("/import", response_model=OemImportOut)
def import_oems(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: PortalUser = Depends(get_current_user),
):
    workbook, rows, indexes = workbook_rows(file)
    result = OemImportOut()
    seen: set[tuple[int, str]] = set()
    try:
        required = ("oem", "vin")
        missing = [name.upper() for name in required if name not in indexes]
        if missing:
            raise HTTPException(400, f"Missing required Excel columns: {', '.join(missing)}")
        vehicle_columns = ("year", "make", "model")
        supplied = [name in indexes for name in vehicle_columns]
        if any(supplied) and not all(supplied):
            raise HTTPException(400, "Provide all three vehicle columns: Year, Make, and Model")

        for row_number, row in enumerate(rows, start=2):
            try:
                with db.begin_nested():
                    if "status" in indexes:
                        status = str(get_cell(row, indexes["status"]) or "").strip()
                        if status.casefold() != "ok":
                            result.skipped += 1
                            continue
                    oem = normalize_text(get_cell(row, indexes["oem"]), "OEM")
                    oem_key = normalized_key(oem)
                    vin_value = normalize_vin(get_cell(row, indexes["vin"]))
                    description_value = get_cell(row, indexes["description"]) if "description" in indexes else None
                    notes_value = get_cell(row, indexes["notes"]) if "notes" in indexes else None
                    description = " ".join(str(description_value or "").strip().split())
                    notes = " ".join(str(notes_value or "").strip().split())

                    if all(supplied):
                        year = validate_year(get_cell(row, indexes["year"]))
                        make = normalize_text(get_cell(row, indexes["make"]), "Make")
                        model = normalize_text(get_cell(row, indexes["model"]), "Model")
                        vehicle, vehicle_created, _ = resolve_vehicle(db, year, make, model, user.id)
                        result.vehicles_created += int(vehicle_created)
                        vin_item = db.scalar(select(Vin).where(
                            Vin.id_vehicle == vehicle.id,
                            Vin.vin_key == vin_value,
                        ))
                        if vin_item is None:
                            vin_item = Vin(id_vehicle=vehicle.id, vin=vin_value, vin_key=vin_value,
                                           created_by=user.id, updated_by=user.id)
                            db.add(vin_item)
                            db.flush()
                            result.vins_created += 1
                    else:
                        matches = db.scalars(select(Vin).where(Vin.vin_key == vin_value).limit(2)).all()
                        if len(matches) > 1:
                            raise ValueError(f"VIN {vin_value} matches multiple vehicles; include Year, Make, and Model")
                        if not matches:
                            raise ValueError(f"VIN {vin_value} was not found; include Year, Make, and Model to create it")
                        vin_item = matches[0]

                    duplicate_key = (vin_item.id, oem_key)
                    if duplicate_key in seen:
                        result.skipped += 1
                        if len(result.errors) < 50:
                            result.errors.append(f"Row {row_number}: duplicate OEM {oem} and VIN {vin_value} in workbook")
                        continue
                    seen.add(duplicate_key)
                    existing = db.scalar(select(Oem).where(Oem.oem_key == oem_key))
                    created = existing is None
                    if existing is None:
                        existing = Oem(oem=oem, oem_key=oem_key, description=description, notes=notes,
                                       created_by=user.id, updated_by=user.id)
                        db.add(existing)
                        db.flush()
                        result.created += 1
                    else:
                        changed = (existing.oem, existing.description, existing.notes) != (oem, description, notes)
                        if changed:
                            existing.oem, existing.description, existing.notes = oem, description, notes
                            existing.updated_by = user.id
                    linked = vin_item not in existing.vins
                    if linked:
                        existing.vins.append(vin_item)
                    if not created:
                        changed = changed or linked
                        result.updated += int(changed)
                        result.skipped += int(not changed)
            except ValueError as error:
                result.skipped += 1
                if len(result.errors) < 50:
                    result.errors.append(f"Row {row_number}: {error}")
        db.commit()
        log_activity(db, user, "import_oems",
                     f"vehicles_created={result.vehicles_created} vins_created={result.vins_created} "
                     f"created={result.created} updated={result.updated} skipped={result.skipped}")
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Import conflicted with a duplicate OEM record") from error
    finally:
        workbook.close()
    return result
