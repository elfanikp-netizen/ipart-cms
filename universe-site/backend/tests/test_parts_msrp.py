import asyncio
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import UploadFile
from openpyxl import Workbook, load_workbook
from sqlalchemy.dialects import sqlite

from app.models import PartsMsrp
from app.routers.ccc_market import (
    _rank_oem_list_crawl,
    export_ccc_oem_list_prices,
    filtered_ccc_records,
    matching_oem_price,
)
from app.routers.parts_msrp import (
    ccc_price_history,
    excel_datetime,
    export_parts_msrp,
    export_parts_msrp_by_list,
    filter_sort_parts_msrp,
    history_previous_values,
    import_parts_msrp,
    list_parts_msrp,
    parse_msrp,
    parts_msrp_export_rows,
)


class PartsMsrpTests(unittest.TestCase):
    def test_grouped_export_keeps_one_oem_snapshot_and_one_fitment(self):
        items = [
            {"oem": "OEM-123", "fitments": ["VIN1", "VIN2"], "msrp": "10"},
            {"oem": "oem-123", "fitments": ["VIN1", "VIN2"], "msrp": "9"},
            {"oem": "OEM-456", "fitments": ["VIN3"], "msrp": "8"},
        ]

        grouped = parts_msrp_export_rows(items, True)
        expanded = parts_msrp_export_rows(items, False)

        self.assertEqual([item["oem"] for item in grouped], ["OEM-123", "OEM-456"])
        self.assertEqual(grouped[0]["fitments"], ["VIN1"])
        self.assertEqual(len(expanded), 3)
        self.assertEqual(expanded[0]["fitments"], ["VIN1", "VIN2"])

    def test_selected_vendor_qualifies_oem_but_all_vendors_are_ranked(self):
        crawl_date = datetime(2026, 10, 31, 19, 19, 29, tzinfo=timezone.utc)
        records = [
            SimpleNamespace(oem="04711S3VA80ZZ", vin="VIN1", crawl_date=crawl_date, market_data={
                "vendor": "iPart Automotive Inc.", "description": "A/M: CAPA", "ext-price": "197.00", "total": "197.00",
            }),
            SimpleNamespace(oem="04711S3VA80ZZ", vin="VIN1", crawl_date=crawl_date, market_data={
                "vendor": "Pacific Auto Company-Ontario", "description": "A/M: CAPA", "ext-price": "198.70", "total": "198.70",
            }),
        ]

        lowest = _rank_oem_list_crawl(records, {"ipart automotive inc."}, {"a/m: capa"}, "ext-price", "lowest")
        highest = _rank_oem_list_crawl(records, {"ipart automotive inc."}, {"a/m: capa"}, "ext-price", "highest")

        self.assertEqual(len(lowest), 1)
        self.assertEqual(lowest[0]["vendor"], "iPart Automotive Inc.")
        self.assertEqual(lowest[0]["price"], Decimal("197.00"))
        self.assertEqual(lowest[0]["second_lowest_vendors"], "Pacific Auto Company-Ontario")
        self.assertEqual(lowest[0]["second_lowest_price"], Decimal("198.70"))
        self.assertEqual(len(highest), 1)
        self.assertEqual(highest[0]["vendor"], "Pacific Auto Company-Ontario")
        self.assertEqual(highest[0]["price"], Decimal("198.70"))
        self.assertEqual(highest[0]["second_lowest_vendors"], "iPart Automotive Inc.")
        self.assertEqual(highest[0]["second_lowest_price"], Decimal("197.00"))

    def test_ccc_description_filter_uses_exact_case_insensitive_match(self):
        statement = filtered_ccc_records(MagicMock(), "", "", "OEM", "", "")
        compiled = statement.compile(dialect=sqlite.dialect())
        sql = str(compiled)

        self.assertIn("lower(trim(universe.ccc_market_data.description)) = ?", sql)
        self.assertNotIn("ccc_market_data.description LIKE", sql)
        self.assertEqual(list(compiled.params.values()), ["oem"])

    def test_ccc_vendor_filter_uses_exact_case_insensitive_match(self):
        statement = filtered_ccc_records(MagicMock(), "", "", "", "iPart Automotive Inc.", "")
        compiled = statement.compile(dialect=sqlite.dialect())
        sql = str(compiled)

        self.assertIn("lower(trim(universe.ccc_market_data.vendor)) = ?", sql)
        self.assertNotIn("ccc_market_data.vendor LIKE", sql)
        self.assertEqual(list(compiled.params.values()), ["ipart automotive inc."])

    def test_ccc_oem_list_export_writes_matching_row_to_ccc_list_sheet(self):
        source = Workbook()
        source.active.append(["OEM Number"])
        source.active.append(["ABC"])
        source.active.append(["NO-DATA"])
        input_content = BytesIO()
        source.save(input_content)
        source.close()
        input_content.seek(0)
        upload = UploadFile(filename="oems.xlsx", file=input_content)
        crawl_date = datetime(2025, 2, 1, tzinfo=timezone.utc)
        record = SimpleNamespace(
            oem="ABC", vin="VIN1", crawl_date=crawl_date,
            market_data={"vendor": "Vendor A", "description": "A/M: CAPA", "ext-price": "50", "total": "55"},
        )
        database = MagicMock()
        database.scalars.return_value.all.return_value = [record]
        with patch("app.routers.ccc_market.log_activity"):
            response = export_ccc_oem_list_prices(
                file=upload,
                vendors=["Vendor A"],
                descriptions=["A/M: CAPA"],
                price_direction="lowest",
                price_field="ext-price",
                db=database,
                user=SimpleNamespace(id=1),
            )

        result = load_workbook(BytesIO(asyncio.run(self.read_response(response))), read_only=True)
        self.assertEqual(result.sheetnames, ["CCC List", "Export Summary"])
        rows = list(result.active.iter_rows(values_only=True))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][0], "ABC")
        self.assertEqual(rows[1][-1], "Matched")
        self.assertEqual(rows[2][0], "NO-DATA")
        self.assertEqual(rows[2][-1], "No CCC data for this OEM")
        summary_rows = list(result["Export Summary"].iter_rows(values_only=True))
        self.assertEqual(summary_rows[1], (2, 1, 1, 1, 0))
        self.assertEqual(summary_rows[-1], ("NO-DATA", "No CCC data for this OEM"))
        result.close()

    def test_oem_list_ranking_uses_latest_crawl_and_selected_total_highest(self):
        earlier = datetime(2025, 1, 1, tzinfo=timezone.utc)
        latest = datetime(2025, 2, 1, tzinfo=timezone.utc)
        records = [
            SimpleNamespace(oem="ABC", vin="VIN1", crawl_date=earlier, market_data={
                "vendor": "Vendor A", "description": "A/M: CAPA", "ext-price": "50", "total": "55",
            }),
            SimpleNamespace(oem="ABC", vin="VIN2", crawl_date=latest, market_data={
                "vendor": "Vendor A", "description": "A/M: CAPA", "ext-price": "80", "total": "90",
            }),
            SimpleNamespace(oem="abc", vin="VIN3", crawl_date=latest, market_data={
                "vendor": "Vendor B", "description": "A/M: CAPA", "ext-price": "100", "total": "110",
            }),
            SimpleNamespace(oem="ABC", vin="VIN4", crawl_date=latest, market_data={
                "vendor": "Unselected", "description": "A/M: CAPA", "ext-price": "1", "total": "2",
            }),
            SimpleNamespace(oem="ABC", vin="VIN5", crawl_date=latest, market_data={
                "vendor": "Vendor B", "description": "OE", "ext-price": "1", "total": "2",
            }),
        ]

        rows = _rank_oem_list_crawl(
            records,
            {"vendor a", "vendor b"},
            {"a/m: capa"},
            "total",
            "highest",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["crawl_date"], latest)
        self.assertEqual(rows[0]["vendor"], "Vendor B")
        self.assertEqual(rows[0]["price"], Decimal("110"))
        self.assertEqual(rows[0]["previous_lowest_price"], Decimal("55"))
        self.assertEqual(rows[0]["outcome"], "Won/Highest")
    def test_ccc_oem_list_uses_latest_crawl_and_selected_price_direction(self):
        earlier = datetime(2025, 1, 1, tzinfo=timezone.utc)
        latest = datetime(2025, 2, 1, tzinfo=timezone.utc)
        records = [
            SimpleNamespace(oem="ABC", vin="VIN1", crawl_date=earlier, market_data={
                "vendor": "Vendor A", "description": "A/M: CAPA", "ext-price": "50", "total": "55",
            }),
            SimpleNamespace(oem="ABC", vin="VIN2", crawl_date=latest, market_data={
                "vendor": "Vendor A", "description": "A/M: CAPA", "ext-price": "80", "total": "90",
            }),
            SimpleNamespace(oem="ABC", vin="VIN3", crawl_date=latest, market_data={
                "vendor": "Vendor B", "description": "A/M: CAPA", "ext-price": "100", "total": "110",
            }),
            SimpleNamespace(oem="ABC", vin="VIN3", crawl_date=latest, market_data={
                "vendor": "Other", "description": "A/M: CAPA", "ext-price": "1", "total": "2",
            }),
        ]
        lowest = _rank_oem_list_crawl(records, {"vendor a", "vendor b"}, {"a/m: capa"}, "ext-price", "lowest")
        highest = _rank_oem_list_crawl(records, {"vendor a", "vendor b"}, {"a/m: capa"}, "total", "highest")

        self.assertEqual(len(lowest), 1)
        self.assertEqual(lowest[0]["crawl_date"], latest)
        self.assertEqual(lowest[0]["vendor"], "Other")
        self.assertEqual(lowest[0]["price"], Decimal("1"))
        self.assertEqual(lowest[0]["second_lowest_vendors"], "Vendor A")
        self.assertEqual(lowest[0]["second_lowest_price"], Decimal("80"))
        self.assertEqual(lowest[0]["previous_lowest_price"], Decimal("50"))
        self.assertEqual(highest[0]["vendor"], "Vendor B")
        self.assertEqual(highest[0]["price"], Decimal("110"))
        self.assertEqual(highest[0]["second_lowest_vendors"], "Vendor A")
        self.assertEqual(highest[0]["second_lowest_price"], Decimal("90"))

    def test_oem_list_export_uses_latest_crawl_with_matching_selected_offer(self):
        older = datetime(2025, 1, 1, tzinfo=timezone.utc)
        latest = datetime(2025, 2, 1, tzinfo=timezone.utc)
        records = [
            SimpleNamespace(oem="ABC", vin="VIN1", crawl_date=older, market_data={
                "vendor": "Vendor A", "description": "A/M: CAPA", "ext-price": "50",
            }),
            SimpleNamespace(oem="ABC", vin="VIN1", crawl_date=latest, market_data={
                "vendor": "Other Vendor", "description": "A/M: CAPA", "ext-price": "40",
            }),
        ]
        rows = _rank_oem_list_crawl(records, {"vendor a"}, {"a/m: capa"}, "ext-price", "lowest")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["crawl_date"], older)
        self.assertEqual(rows[0]["vendor"], "Vendor A")

    def test_timezone_aware_export_date_is_excel_compatible(self):
        value = datetime(2025, 1, 2, 12, tzinfo=timezone.utc)
        self.assertEqual(excel_datetime(value), datetime(2025, 1, 2, 12))

    def test_current_export_generates_workbook_with_timezone_aware_date(self):
        item = {
            "oem": "ABC123", "fitments": [], "msrp": "99.50",
            "previous_msrp": None, "ccc_price": None, "previous_ccc_price": None,
            "gap_msrp": None, "gap_ccc": None,
            "crawl_date": datetime(2025, 1, 2, tzinfo=timezone.utc),
        }
        with patch("app.routers.parts_msrp.parts_msrp_items", return_value=[item]), patch(
            "app.routers.parts_msrp.log_activity"
        ):
            response = export_parts_msrp(
                db=MagicMock(), user=SimpleNamespace(id=1)
            )

        content = asyncio.run(self.read_response(response))
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        rows = list(workbook.active.iter_rows(values_only=True))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "ABC123")
        workbook.close()

    def test_oem_list_export_generates_workbook_with_timezone_aware_date(self):
        upload_workbook = Workbook()
        upload_workbook.active.append(["OEM Number"])
        upload_workbook.active.append(["ABC123"])
        upload_content = BytesIO()
        upload_workbook.save(upload_content)
        upload_workbook.close()
        upload_content.seek(0)
        upload = UploadFile(filename="oem-list.xlsx", file=upload_content)
        record = SimpleNamespace(oem="ABC123", crawl_date=datetime(2025, 1, 2, tzinfo=timezone.utc))
        item = {
            "oem": "ABC123", "fitments": [], "msrp": "99.50",
            "previous_msrp": None, "ccc_price": None, "previous_ccc_price": None,
            "gap_msrp": None, "gap_ccc": None,
            "crawl_date": datetime(2025, 1, 2, tzinfo=timezone.utc),
        }
        database = MagicMock()
        database.scalars.return_value.all.return_value = [record]
        with patch("app.routers.parts_msrp.enrich_parts_msrp_records", return_value=[item]), patch(
            "app.routers.parts_msrp.log_activity"
        ):
            response = export_parts_msrp_by_list(
                file=upload, db=database, user=SimpleNamespace(id=1)
            )

        content = asyncio.run(self.read_response(response))
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        rows = list(workbook.active.iter_rows(values_only=True))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "ABC123")
        workbook.close()

    def test_list_passes_crawl_date_range_to_shared_filter(self):
        from_date = datetime(2025, 1, 1).date()
        to_date = datetime(2025, 1, 31).date()
        rows = [{"id": 1, "oem": "ABC123", "crawl_date": datetime(2025, 1, 15)}]
        with patch("app.routers.parts_msrp.parts_msrp_items", return_value=rows) as get_items:
            response = list_parts_msrp(
                page=1,
                page_size=25,
                from_date=from_date,
                to_date=to_date,
                db=MagicMock(),
                _=SimpleNamespace(id=1),
            )

        self.assertEqual(get_items.call_args.args[1], "")
        self.assertEqual(get_items.call_args.args[5:], (from_date, to_date))
        self.assertEqual(response["items"], rows)

    @staticmethod
    async def read_response(response):
        return b"".join([chunk async for chunk in response.body_iterator])

    def test_column_filters_and_numeric_sort_apply_to_enriched_rows(self):
        rows = [
            {"oem": "OEM-B", "fitments": ["2020 Ford Focus"], "msrp": "200.00", "previous_msrp": None},
            {"oem": "OEM-A", "fitments": ["2021 Honda Civic"], "msrp": "100.00", "previous_msrp": "90.00"},
        ]

        filtered = filter_sort_parts_msrp(
            rows,
            '{"fitments":{"value":"honda","mode":"any"}}',
            "msrp",
            "desc",
        )
        self.assertEqual([row["oem"] for row in filtered], ["OEM-A"])

        sorted_rows = filter_sort_parts_msrp(rows, "", "msrp", "asc")
        self.assertEqual([row["msrp"] for row in sorted_rows], ["100.00", "200.00"])

    def test_empty_column_filter_selects_missing_previous_price(self):
        rows = [
            {"id": 1, "oem": "OEM-A", "crawl_date": datetime(2025, 1, 1), "previous_ccc_price": None},
            {"id": 2, "oem": "OEM-B", "crawl_date": datetime(2025, 1, 1), "previous_ccc_price": "50.00"},
        ]
        filtered = filter_sort_parts_msrp(
            rows,
            '{"previous_ccc_price":{"value":"","mode":"empty"}}',
            "",
            "asc",
        )
        self.assertEqual([row["oem"] for row in filtered], ["OEM-A"])

    def test_parse_msrp_accepts_currency_and_excel_numeric_values(self):
        self.assertEqual(parse_msrp("$1,299.5"), Decimal("1299.50"))
        self.assertEqual(parse_msrp(799), Decimal("799.00"))
        with self.assertRaisesRegex(ValueError, "valid number"):
            parse_msrp("not a price")

    def test_matching_ccc_oem_offer_uses_exact_oem_description_and_lowest_price(self):
        offers = [
            {"description": "OEM", "ext-price": "$125.00"},
            {"description": "OEM", "ext-price": "$119.50"},
            {"description": "OEM CAPA", "ext-price": "$80.00"},
        ]
        self.assertEqual(matching_oem_price(offers), Decimal("119.50"))
        self.assertIsNone(matching_oem_price([{"description": "CAPA", "ext-price": "80"}]))

    def test_msrp_history_uses_the_immediately_previous_date(self):
        newest = SimpleNamespace(id=3, oem="ABC", crawl_date=datetime(2025, 1, 1, tzinfo=timezone.utc), msrp=Decimal("30"))
        middle = SimpleNamespace(id=2, oem="abc", crawl_date=datetime(2024, 1, 1, tzinfo=timezone.utc), msrp=Decimal("20"))
        oldest = SimpleNamespace(id=1, oem="ABC", crawl_date=datetime(2023, 1, 1, tzinfo=timezone.utc), msrp=Decimal("10"))
        previous = history_previous_values([newest, oldest, middle])
        self.assertEqual(previous, {3: Decimal("20"), 2: Decimal("10"), 1: None})

    def test_ccc_history_collapses_same_date_and_uses_previous_crawl(self):
        latest = datetime(2025, 2, 1, tzinfo=timezone.utc)
        earlier = datetime(2025, 1, 1, tzinfo=timezone.utc)
        records = [
            SimpleNamespace(oem="ABC", crawl_date=latest, market_data={"description": "OEM", "ext-price": "120"}),
            SimpleNamespace(oem="abc", crawl_date=latest, market_data={"description": "OEM", "ext-price": "115"}),
            SimpleNamespace(oem="ABC", crawl_date=earlier, market_data={"description": "OEM", "ext-price": "100"}),
        ]
        self.assertEqual(ccc_price_history(records), {"abc": (Decimal("115"), Decimal("100"))})

    def test_import_accepts_oem_aliases_and_only_writes_parts_msrp(self):
        for oem_header in ("oEm", "OEM Number"):
            with self.subTest(oem_header=oem_header):
                workbook = Workbook()
                sheet = workbook.active
                sheet.append([oem_header, "MsRp", "dAtE"])
                sheet.append(["abc123", "$99.50", datetime(2025, 1, 2)])
                sheet.append(["", "$75.00", datetime(2025, 1, 2)])
                sheet.append(["def456", "", datetime(2025, 1, 2)])
                content = BytesIO()
                workbook.save(content)
                workbook.close()
                content.seek(0)
                upload = UploadFile(filename="parts-msrp.xlsx", file=content)

                session = MagicMock()
                session.begin_nested.return_value = nullcontext()
                session.scalar.return_value = None

                with patch("app.routers.parts_msrp.log_activity"):
                    summary = import_parts_msrp(upload, session, SimpleNamespace(id=1))

                writes = [call.args[0] for call in session.add.call_args_list]
                self.assertEqual(len(writes), 1)
                self.assertIsInstance(writes[0], PartsMsrp)
                self.assertEqual(writes[0].oem, "ABC123")
                self.assertEqual(writes[0].msrp, Decimal("99.50"))
                self.assertEqual(summary, {"created": 1, "updated": 0, "skipped": 2, "errors": []})
                session.commit.assert_called_once_with()

    def test_import_skips_identical_snapshot_and_updates_changed_msrp(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["OEM", "MSRP", "Date"])
        sheet.append(["abc123", "$99.50", datetime(2025, 1, 2)])
        sheet.append(["ABC123", "$120.00", datetime(2025, 1, 2)])
        content = BytesIO()
        workbook.save(content)
        workbook.close()
        content.seek(0)
        upload = UploadFile(filename="parts-msrp.xlsx", file=content)

        existing = SimpleNamespace(msrp=Decimal("99.50"))
        session = MagicMock()
        session.begin_nested.return_value = nullcontext()
        session.scalar.return_value = existing

        with patch("app.routers.parts_msrp.log_activity"):
            summary = import_parts_msrp(upload, session, SimpleNamespace(id=1))

        self.assertEqual(existing.msrp, Decimal("120.00"))
        session.add.assert_not_called()
        self.assertEqual(summary, {"created": 0, "updated": 1, "skipped": 1, "errors": []})
        session.commit.assert_called_once_with()

    def test_export_by_list_accepts_oem_and_oem_number_headers(self):
        for header in ("oEm", "OEM Number"):
            with self.subTest(header=header):
                workbook = Workbook()
                workbook.active.append([header])
                workbook.active.append([" abc123 "])
                content = BytesIO()
                workbook.save(content)
                workbook.close()
                content.seek(0)
                upload = UploadFile(filename="oem-list.xlsx", file=content)

                session = MagicMock()
                session.scalars.return_value.all.return_value = []
                with patch("app.routers.parts_msrp.log_activity"):
                    response = export_parts_msrp_by_list(
                        file=upload, db=session, user=SimpleNamespace(id=1)
                    )

                statement = session.scalars.call_args.args[0]
                self.assertIn("abc123", str(statement.compile().params).casefold())
                self.assertEqual(response.headers["content-disposition"], 'attachment; filename="parts-msrp-by-oem.xlsx"')


if __name__ == "__main__":
    unittest.main()
