from io import BytesIO
from pathlib import Path
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, UploadFile
from openpyxl import Workbook, load_workbook

from app.crawlers import CRAWLERS
from app.routers.runs import create_run, part_type_input_rows, part_type_options, part_type_run_workbook


def input_workbook(headers, rows):
    workbook = Workbook()
    workbook.active.append(headers)
    for row in rows:
        workbook.active.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


class CccPartTypeRunTests(unittest.TestCase):
    def test_vin_validation(self):
        self.assertEqual(part_type_input_rows(input_workbook(["VIN"], [["VIN1"], ["VIN2"]]), ".xlsx"), ([], ["VIN1", "VIN2"]))
        errors, _ = part_type_input_rows(input_workbook(["Other"], [["value"]]), ".xlsx")
        self.assertIn("VIN", errors[0])
        errors, _ = part_type_input_rows(input_workbook(["VIN", "Other"], [[None, "value"]]), ".xlsx")
        self.assertIn("Row 2", errors[0])

    def test_snapshot_expands_phrases_per_vin(self):
        records = [SimpleNamespace(part_type_code="101", part_type_description="Bumper", scenario="FRONT BUMPER, COVER, "),
                   SimpleNamespace(part_type_code="109", part_type_description="Cooling", scenario="COOLING")]
        content = part_type_run_workbook(["VIN1", "VIN2"], records)
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        try:
            rows = list(workbook.active.values)
        finally:
            workbook.close()
        self.assertEqual(rows[1:4], [("VIN1", "101", "Bumper", "FRONT BUMPER"),
                                     ("VIN1", "101", "Bumper", "COVER"),
                                     ("VIN1", "109", "Cooling", "COOLING")])
        self.assertEqual(len(rows), 7)

    def test_options_put_usable_scenarios_first(self):
        records = [SimpleNamespace(id=1, part_type_code="100", part_type_description="A", scenario=""),
                   SimpleNamespace(id=2, part_type_code="101", part_type_description="B", scenario="cover"),
                   SimpleNamespace(id=3, part_type_code="102", part_type_description="C", scenario=", ,")]
        session = MagicMock()
        session.scalars.return_value.all.return_value = records
        self.assertEqual([item["part_type_code"] for item in part_type_options(session, None)], ["101", "100", "102"])

    def test_crawler_receives_new_action(self):
        args = CRAWLERS["ccc"].build_args({"search_action": "vin_part_type_scenario"}, Path("input.xlsx"), Path("output.xlsx"))
        self.assertEqual(args[args.index("--search-action") + 1], "vin_part_type_scenario")


class CccPartTypeQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_snapshots_selected_scenarios(self):
        record = SimpleNamespace(id=4, part_type_code="101", part_type_description="Bumper", scenario="FRONT BUMPER, COVER")
        database = MagicMock()
        database.scalars.return_value.all.return_value = [record]
        database.add.side_effect = lambda run: setattr(run, "id", 77)
        user = SimpleNamespace(id=1)
        content = input_workbook(["VIN"], [["VIN1"]])
        with tempfile.TemporaryDirectory() as directory, patch("app.routers.runs.settings.data_dir", Path(directory)), \
             patch("app.routers.runs.runner.enqueue") as enqueue, patch("app.routers.runs.log_activity"), \
             patch("app.routers.runs.to_out", return_value={"id": 77}):
            result = await create_run(crawler_id="ccc", file=UploadFile(filename="input.xlsx", file=BytesIO(content)),
                                      column="", site="cccone", search_action="vin_part_type_scenario", part_type_ids="[4]",
                                      description="A/M: CAPA", limit=0, delay=1.5, fresh=False, show=False, debug=False,
                                      manual_login=False, idempotency_key=None, db=database, user=user)
            self.assertEqual(result, {"id": 77})
            enqueue.assert_called_once_with(77)
            saved = load_workbook(Path(directory) / "runs" / "77" / "input.xlsx", read_only=True, data_only=True)
            try:
                self.assertEqual([row[-1] for row in list(saved.active.values)[1:]], ["FRONT BUMPER", "COVER"])
            finally:
                saved.close()
            run = database.add.call_args.args[0]
            self.assertEqual(json.loads(run.params)["part_type_ids"], [4])
            self.assertEqual(json.loads(run.params)["part_types"], [
                {"code": "101", "description": "Bumper", "scenario": "FRONT BUMPER, COVER"}
            ])

    async def test_queue_rejects_empty_scenario(self):
        database = MagicMock()
        database.scalars.return_value.all.return_value = [SimpleNamespace(id=4, scenario=" , ")]
        with self.assertRaises(HTTPException) as error:
            await create_run(crawler_id="ccc", file=UploadFile(filename="input.xlsx", file=BytesIO(input_workbook(["VIN"], [["VIN1"]]))),
                             column="", site="cccone", search_action="vin_part_type_scenario", part_type_ids="[4]",
                             description="", limit=0, delay=1.5, fresh=False, show=False, debug=False,
                             manual_login=False, idempotency_key=None, db=database, user=SimpleNamespace(id=1))
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()