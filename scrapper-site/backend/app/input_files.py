"""Excel input inspection and template generation for crawler runs."""

from __future__ import annotations

from io import BytesIO
import re

import xlrd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from .crawlers import CrawlerSpec


def normalize_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def inspect_workbook(content: bytes, suffix: str) -> tuple[list[str], bool]:
    """Return the first-row headers and whether the active sheet has any data rows."""
    extension = suffix.casefold()
    if extension == ".xls":
        workbook = xlrd.open_workbook(file_contents=content, on_demand=True)
        try:
            if workbook.nsheets == 0:
                return [], False
            sheet = workbook.sheet_by_index(0)
            headers = [str(value or "").strip() for value in (sheet.row_values(0) if sheet.nrows else [])]
            has_data = any(
                any(str(value or "").strip() for value in sheet.row_values(row_index))
                for row_index in range(1, sheet.nrows)
            )
            return headers, has_data
        finally:
            workbook.release_resources()

    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    try:
        if not workbook.worksheets:
            return [], False
        rows = workbook.active.iter_rows(values_only=True)
        headers = [str(value or "").strip() for value in next(rows, ())]
        has_data = any(any(str(value or "").strip() for value in row) for row in rows)
        return headers, has_data
    finally:
        workbook.close()


def _column_exists(headers: list[str], selector: str) -> bool:
    wanted = normalize_header(selector)
    if any(normalize_header(header) == wanted for header in headers):
        return True
    token = selector.strip().upper()
    if token.isdigit():
        index = int(token) - 1
    elif token and re.fullmatch(r"[A-Z]+", token):
        index = 0
        for character in token:
            index = index * 26 + ord(character) - ord("A") + 1
        index -= 1
    else:
        return False
    return 0 <= index < len(headers) and bool(headers[index].strip())


def validate_input(
    spec: CrawlerSpec,
    site: str,
    column: str,
    headers: list[str],
    has_data: bool,
) -> list[str]:
    errors = []
    normalized_headers = {normalize_header(header) for header in headers if header.strip()}
    input_spec = spec.input_for_site(site)

    missing = [
        header for header in input_spec.required_headers
        if normalize_header(header) not in normalized_headers
    ]
    if missing:
        errors.append(f"Missing required header(s): {', '.join(missing)}.")

    if column.strip():
        if not _column_exists(headers, column):
            errors.append(f"Selected column '{column.strip()}' was not found in the header row.")
    elif spec.column_required:
        errors.append("Select the column containing the values to search.")

    if not column.strip() or not input_spec.allow_custom_column:
        for alternatives in input_spec.header_alternatives:
            if not any(normalize_header(header) in normalized_headers for header in alternatives):
                choices = " or ".join(alternatives)
                errors.append(f"Add a recognized search-column header ({choices}) or select a column.")

    if not headers or not any(header.strip() for header in headers):
        errors.append("The first worksheet must have a header row.")
    if not has_data:
        errors.append("The first worksheet has no data rows.")
    return errors


def create_template(spec: CrawlerSpec, site: str) -> bytes:
    headers = spec.input_for_site(site).template_headers
    if not headers:
        headers = ("Search Value",)
    workbook = Workbook()
    try:
        sheet = workbook.active
        sheet.title = "Input"
        sheet.append(list(headers))
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            sheet.column_dimensions[cell.column_letter].width = max(16, len(str(cell.value)) + 4)
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()
