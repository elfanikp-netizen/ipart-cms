from io import BytesIO
from pathlib import Path
import unittest

from openpyxl import Workbook, load_workbook

from app.crawlers import CRAWLERS
from app.input_files import carid_input_mode, create_template, inspect_workbook, resolve_column_header, validate_input


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

    def test_carid_routes_by_selected_or_detected_input_column(self) -> None:
        spec = CRAWLERS["carid"]
        headers = ["PARTSLINK", "Cross Reference"]

        self.assertEqual(carid_input_mode(headers, "B"), "interchange")
        self.assertEqual(carid_input_mode(["Interchange Number"], ""), "interchange")
        self.assertEqual(carid_input_mode(headers, ""), "partslink")
        self.assertEqual(validate_input(spec, "carid", "", ["Interchange"], True), [])
        self.assertEqual(resolve_column_header(headers, "B"), "Cross Reference")
        self.assertEqual(spec.resolve_script("carid", "interchange").name, "carid_interchange_scraper.py")
        self.assertEqual(spec.resolve_script("carid", "partslink").name, "carid_scraper.py")
        args = spec.build_args(
            {"site": "carid", "input_mode": "interchange", "column": "B", "resolved_column": "Cross Reference"},
            Path("input.xlsx"),
            Path("output.xlsx"),
        )
        self.assertEqual(Path(args[0]).name, "carid_interchange_scraper.py")
        self.assertEqual(args[args.index("--column") + 1], "Cross Reference")

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
                self.assertTrue(spec.to_dict()["output_columns"])

    def test_crawler_names_and_output_columns_are_exposed(self) -> None:
        self.assertEqual(CRAWLERS["ccc"].name, "CCC Workfile")
        self.assertEqual(CRAWLERS["keystone-model"].name, "Keystone by Brand")
        self.assertEqual(
            CRAWLERS["brand-ford"].to_dict()["output_columns"],
            ["OEM Number", "MSRP", "Date", "Status"],
        )
        self.assertIn("Ipart List Price CCC", CRAWLERS["ccc"].to_dict()["output_columns"])
        self.assertIn("Product URL", CRAWLERS["carid"].to_dict()["output_columns"])
        vin_sites = {site["key"]: site for site in CRAWLERS["vin-lookup"].to_dict()["sites"]}
        self.assertEqual(vin_sites["vininspect"]["output_columns"], ["Year", "Make", "Model", "VIN", "Status"])
        self.assertEqual(vin_sites["google"]["output_columns"], ["VIN", "VIN_Source", "VIN_Candidates", "VIN_Status"])

    def test_every_site_option_label_includes_its_domain(self) -> None:
        for crawler_id, crawler in CRAWLERS.items():
            for site in crawler.to_dict()["sites"]:
                with self.subTest(crawler=crawler_id, site=site["key"]):
                    self.assertRegex(site["label"], r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


if __name__ == "__main__":
    unittest.main()
