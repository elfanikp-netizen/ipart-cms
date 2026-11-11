import asyncio
from io import BytesIO
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import UploadFile
from openpyxl import Workbook, load_workbook

from app.routers.catalogs import (
    catalog_pair_export_headers,
    catalog_pair_export_row,
    export_catalog_by_list,
)
from app.routers.oem import export_oems_by_list, row_out


def upload_workbook(headers, values):
    workbook = Workbook()
    workbook.active.append(headers)
    workbook.active.append(values)
    content = BytesIO()
    workbook.save(content)
    workbook.close()
    content.seek(0)
    return UploadFile(filename="export-list.xlsx", file=content)


def response_rows(response):
    async def read_body():
        return b"".join([chunk async for chunk in response.body_iterator])

    content = BytesIO(asyncio.run(read_body()))
    workbook = load_workbook(content, read_only=True, data_only=True)
    try:
        return list(workbook.active.iter_rows(values_only=True))
    finally:
        workbook.close()


class MasterDataExportTests(unittest.TestCase):
    def test_cross_reference_export_adds_one_oem_column_per_shared_oem(self):
        oems = ["OEM-4", "OEM-2", "OEM-1", "OEM-3"]
        pair = (1, 2)
        mapping = {pair: oems}

        headers = catalog_pair_export_headers(mapping)
        row = catalog_pair_export_row("P-100", "I-200", oems, len(headers) - 3)

        self.assertEqual(headers, [
            "PARTSLINK", "INTERCHANGE", "SHARED OEM PARTS", "OEM1", "OEM2", "OEM3", "OEM4",
        ])
        self.assertEqual(row, ["P-100", "I-200", 4, "OEM-1", "OEM-2", "OEM-3", "OEM-4"])

    def test_catalog_export_can_select_interchange_list(self):
        oem = SimpleNamespace(oem="OEM-1", oem_key="oem-1", description="OEM description", partslinks=[])
        target = SimpleNamespace(partslink="P-100", partslink_key="p-100", description="Parts description")
        oem.partslinks = [target]
        source = SimpleNamespace(interchange="I-200", interchange_key="i-200", oems=[oem])
        session = MagicMock()
        session.scalars.return_value.all.return_value = [source]
        user = SimpleNamespace(id=1)

        with patch("app.routers.catalogs.log_activity"):
            response = export_catalog_by_list(
                "partslinks", upload_workbook(["Interchange Number"], ["I-200"]),
                "interchange", session, user,
            )

        rows = response_rows(response)
        self.assertEqual(rows[0], ("INTERCHANGE", "PARTSLINK", "OEM", "Description"))
        self.assertEqual(rows[1], ("I-200", "P-100", "OEM-1", "OEM description"))

    def test_catalog_export_keeps_existing_oem_list_workbook_shape(self):
        oem = SimpleNamespace(oem="OEM-1", oem_key="oem-1", description="OEM description", partslinks=[])
        target = SimpleNamespace(partslink="P-100", partslink_key="p-100", description="Parts description")
        oem.partslinks = [target]
        session = MagicMock()
        session.scalars.return_value.all.return_value = [oem]
        user = SimpleNamespace(id=1)

        with patch("app.routers.catalogs.log_activity"):
            response = export_catalog_by_list(
                "partslinks", upload_workbook(["oEm"], ["OEM-1"]), "oem", session, user,
            )

        rows = response_rows(response)
        self.assertEqual(rows[0], ("PARTSLINK", "OEM", "Description"))
        self.assertEqual(rows[1], ("P-100", "OEM-1", "OEM description"))

    def test_oem_export_can_select_partslink_list_and_expand_vin_fitment(self):
        vehicle = SimpleNamespace(year=2020, make="Ford", model="Explorer")
        vin = SimpleNamespace(id=1, vin="1FM5K8", vin_key="1fm5k8", vehicle=vehicle)
        partslink = SimpleNamespace(partslink="P-100")
        interchange = SimpleNamespace(interchange="I-200")
        oem = SimpleNamespace(
            id=1, oem="OEM-1", oem_key="oem-1", description="Headlamp", notes="", vins=[vin],
            partslinks=[partslink], interchanges=[interchange],
        )
        source = SimpleNamespace(partslink="P-100", partslink_key="p-100", oems=[oem])
        session = MagicMock()
        session.scalars.return_value.all.return_value = [source]
        user = SimpleNamespace(id=1)

        with patch("app.routers.oem.log_activity"):
            response = export_oems_by_list(
                upload_workbook(["Partslink Number"], ["P-100"]), "partslink", session, user,
            )

        rows = response_rows(response)
        self.assertEqual(rows[0], (
            "PARTSLINK", "OEM", "VIN", "Year", "Make", "Model", "Partslink", "Interchange",
            "Is Valid", "Description", "Notes",
        ))
        self.assertEqual(rows[1], (
            "P-100", "OEM-1", "1FM5K8", 2020, "Ford", "Explorer", "P-100", "I-200",
            False, "Headlamp", None,
        ))

    def test_oem_list_export_groups_by_oem_by_default_and_can_expand_vins(self):
        vins = [
            SimpleNamespace(id=1, vin="VIN-1", vin_key="vin-1", vehicle=SimpleNamespace(year=2020, make="Ford", model="Focus")),
            SimpleNamespace(id=2, vin="VIN-2", vin_key="vin-2", vehicle=SimpleNamespace(year=2021, make="Ford", model="Escape")),
        ]
        oem = SimpleNamespace(
            id=1, oem="OEM-1", oem_key="oem-1", description="Part", notes="", vins=vins,
            partslinks=[], interchanges=[],
        )
        session = MagicMock()
        session.scalars.return_value.all.return_value = [oem]
        user = SimpleNamespace(id=1)

        with patch("app.routers.oem.log_activity"):
            grouped = export_oems_by_list(
                upload_workbook(["OEM"], ["OEM-1"]), "oem", session, user,
            )
            expanded = export_oems_by_list(
                upload_workbook(["OEM"], ["OEM-1"]), "oem", session, user,
                group_by_type=False,
            )

        self.assertEqual(len(response_rows(grouped)), 2)
        self.assertEqual(len(response_rows(expanded)), 3)

    def test_grouped_oem_list_export_prefers_valid_vin_fitment(self):
        vins = [
            SimpleNamespace(vin="VIN-1", vin_key="vin-1", id=1, vehicle=SimpleNamespace(year=2020, make="Ford", model="Focus")),
            SimpleNamespace(vin="VIN-2", vin_key="vin-2", id=2, vehicle=SimpleNamespace(year=2021, make="Ford", model="Escape")),
        ]
        oem = SimpleNamespace(
            id=1, oem="OEM-1", oem_key="oem-1", description="Part", notes="", vins=vins,
            partslinks=[], interchanges=[],
        )
        session = MagicMock()
        session.scalars.return_value.all.return_value = [oem]

        with patch("app.routers.oem.load_fitment_validity", return_value={(1, 1): False, (1, 2): True}), patch(
            "app.routers.oem.log_activity"
        ):
            response = export_oems_by_list(
                upload_workbook(["OEM"], ["OEM-1"]), "oem", session, SimpleNamespace(id=1),
            )

        rows = response_rows(response)
        self.assertEqual(rows[1][1], "VIN-2")
        self.assertIs(rows[1][7], True)

    def test_oem_api_payload_includes_per_fitment_validity(self):
        vin = SimpleNamespace(id=3, vin="VIN-3", vin_key="vin-3", vehicle=SimpleNamespace(year=2020, make="Ford", model="Focus"))
        now = datetime.now(timezone.utc)
        oem = SimpleNamespace(
            id=4, oem="OEM-4", description="Part", notes="", vins=[vin],
            partslinks=[], interchanges=[], created_at=now, updated_at=now,
        )

        result = row_out(oem, {(4, 3): True})

        self.assertTrue(result.vins[0].is_valid)

    def test_catalog_list_export_groups_by_catalog_type_and_can_expand_mappings(self):
        target = SimpleNamespace(partslink="P-100", partslink_key="p-100", description="Catalog description")
        oems = [
            SimpleNamespace(oem="OEM-1", oem_key="oem-1", description="OEM one", partslinks=[target]),
            SimpleNamespace(oem="OEM-2", oem_key="oem-2", description="OEM two", partslinks=[target]),
        ]
        target.oems = oems
        session = MagicMock()
        session.scalars.return_value.all.return_value = [target]
        user = SimpleNamespace(id=1)

        with patch("app.routers.catalogs.log_activity"):
            grouped = export_catalog_by_list(
                "partslinks", upload_workbook(["Partslink"], ["P-100"]), "partslink", session, user,
            )
            expanded = export_catalog_by_list(
                "partslinks", upload_workbook(["Partslink"], ["P-100"]), "partslink", session, user,
                group_by_type=False,
            )

        self.assertEqual(len(response_rows(grouped)), 2)
        self.assertEqual(len(response_rows(expanded)), 3)


if __name__ == "__main__":
    unittest.main()
