import unittest

from openpyxl import Workbook

from app.routers.catalogs import open_workbook
from app.routers.master_data import excel_indexes, normalize_excel_header


class ExcelHeaderTests(unittest.TestCase):
    def test_header_normalization_ignores_case_and_separators(self):
        variants = ("OEM1", "oem1", "oEm1", "OEM 1", "OEM-1")

        self.assertEqual({normalize_excel_header(value) for value in variants}, {"oem1"})

    def test_required_column_indexes_accept_mixed_case_numbered_headers(self):
        self.assertEqual(
            excel_indexes(["oEm1", "mAkE"], ("OEM 1", "Make")),
            {"OEM 1": 0, "Make": 1},
        )

    def test_catalog_workbook_indexes_accept_compact_oem_headers(self):
        workbook = Workbook()
        workbook.active.append(["pArTsLiNk", "oEm1", "iNtErChAnGe1"])
        content = __import__("io").BytesIO()
        workbook.save(content)
        workbook.close()
        content.seek(0)

        from fastapi import UploadFile

        uploaded = UploadFile(filename="catalog.xlsx", file=content)
        loaded, _rows, indexes = open_workbook(uploaded)
        try:
            self.assertEqual(indexes[normalize_excel_header("OEM 1")], 1)
            self.assertEqual(indexes[normalize_excel_header("Interchange 1")], 2)
        finally:
            loaded.close()


if __name__ == "__main__":
    unittest.main()