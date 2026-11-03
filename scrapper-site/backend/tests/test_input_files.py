from io import BytesIO
import unittest

from openpyxl import Workbook, load_workbook

from app.crawlers import CRAWLERS
from app.input_files import create_template, inspect_workbook, validate_input


def workbook_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


class InputFileTests(unittest.TestCase):
    def test_inspect_workbook_returns_headers_and_data_state(self) -> None:
        content = workbook_bytes([" VIN ", "OEM"], [["1HGCM82633A004352", "12345"]])

        headers, has_data = inspect_workbook(content, ".xlsx")

        self.assertEqual(headers, ["VIN", "OEM"])
        self.assertTrue(has_data)

    def test_ccc_requires_vin_and_oem_headers(self) -> None:
        spec = CRAWLERS["ccc"]

        self.assertEqual(validate_input(spec, "cccone", "", ["VIN", "OEM"], True), [])
        issues = validate_input(spec, "cccone", "", ["VIN"], True)
        self.assertTrue(any("OEM" in issue for issue in issues))

    def test_selected_custom_column_is_checked(self) -> None:
        spec = CRAWLERS["carid"]

        self.assertEqual(validate_input(spec, "carid", "My Parts", ["My Parts"], True), [])
        issues = validate_input(spec, "carid", "Missing", ["My Parts"], True)
        self.assertTrue(any("Missing" in issue for issue in issues))

    def test_pacific_best_requires_a_supported_search_header(self) -> None:
        spec = CRAWLERS["pacific-best"]

        self.assertEqual(validate_input(spec, "pacificbest", "PARTSLINK", ["PARTSLINK", "OEM"], True), [])
        issues = validate_input(spec, "pacificbest", "Custom", ["Custom"], True)
        self.assertTrue(any("PARTSLINK or OEM" in issue for issue in issues))

    def test_required_column_and_data_rows_are_checked(self) -> None:
        spec = CRAWLERS["brand-ford"]

        self.assertTrue(validate_input(spec, "ford", "", ["OEM Number"], True))
        self.assertTrue(validate_input(spec, "ford", "OEM Number", ["OEM Number"], False))

    def test_template_uses_site_specific_headers(self) -> None:
        spec = CRAWLERS["keystone-model"]
        content = create_template(spec, "orderkeystone")
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        try:
            headers = list(next(workbook.active.iter_rows(values_only=True)))
        finally:
            workbook.close()

        self.assertEqual(headers, ["Year", "Brand", "Model", "Parts", "Category"])

    def test_every_registered_crawler_has_a_template_schema(self) -> None:
        for crawler_id, spec in CRAWLERS.items():
            with self.subTest(crawler=crawler_id):
                self.assertTrue(spec.input_for_site(None).template_headers)


if __name__ == "__main__":
    unittest.main()
