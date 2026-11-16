from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import inspect

from .models import CccScenarioPartType


def initialize_part_types(engine, path: Path) -> None:
    table = CccScenarioPartType.__table__
    if inspect(engine).has_table(table.name, schema=table.schema):
        return

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        rows = workbook["Master Hollander Codes"].iter_rows(values_only=True)
        headers = ("Part Type Code", "Part Type Description", "Subsystem Category", "Series Group", "Reference Notes")
        for row in rows:
            if tuple(row[:len(headers)]) == headers:
                break
        else:
            raise ValueError("Part type workbook headers not found")
        fields = ("part_type_code", "part_type_description", "subsystem_category", "series_group", "reference_notes")
        records = []
        for row in rows:
            if not any(value is not None and str(value).strip() for value in row[:len(fields)]):
                continue
            values = [str(value).strip() if value is not None else "" for value in row[:len(fields)]]
            if not values[0]:
                raise ValueError("Part type workbook contains a row without a code")
            records.append(dict(zip(fields, values)))
        if not records:
            raise ValueError("Part type workbook contains no records")
    finally:
        workbook.close()

    with engine.begin() as connection:
        table.create(connection)
        connection.execute(table.insert(), records)