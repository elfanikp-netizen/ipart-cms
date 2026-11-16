import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session

from app.models import CccScenarioPartType
from app.part_type_seed import initialize_part_types
from app.routers.ccc_scenarios import create_part_type, delete_part_type, list_part_types, update_part_type
from app.schemas import CccScenarioPartTypeIn


class CccPartTypeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", execution_options={"schema_translate_map": {"scrapping": None}})
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "types.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Master Hollander Codes"
        sheet.append(["Title"])
        sheet.append(["Part Type Code", "Part Type Description", "Subsystem Category", "Series Group", "Reference Notes"])
        sheet.append(["001", "First", "Body", "100", "Note"])
        sheet.append(["002", "Second", "Engine", "200", ""])
        workbook.save(self.path)
        workbook.close()

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def initialize(self):
        sqlite_inspector = inspect(self.engine)
        with patch("app.part_type_seed.inspect", return_value=SimpleNamespace(
            has_table=lambda name, schema=None: sqlite_inspector.has_table(name)
        )):
            initialize_part_types(self.engine, self.path)

    def test_seed_and_restart_preserve_changes(self):
        self.initialize()
        with Session(self.engine) as session:
            rows = session.scalars(select(CccScenarioPartType).order_by(CccScenarioPartType.id)).all()
            self.assertEqual([(row.part_type_code, row.part_type_description, row.scenario) for row in rows],
                             [("001", "First", ""), ("002", "Second", "")])
            rows[0].scenario = "changed"
            session.delete(rows[1])
            session.commit()
        self.initialize()
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(CccScenarioPartType)), 1)
            self.assertEqual(session.scalar(select(CccScenarioPartType)).scenario, "changed")

    def test_crud_search_and_validation(self):
        self.initialize()
        user = SimpleNamespace(id=1)
        with Session(self.engine) as session, patch("app.routers.ccc_scenarios.log_activity"):
            created = create_part_type(CccScenarioPartTypeIn(part_type_code=" 003 ", scenario=" new "), session, user)
            self.assertEqual((created["part_type_code"], created["scenario"]), ("003", "new"))
            updated = update_part_type(created["id"], CccScenarioPartTypeIn(part_type_code="003", scenario="edited"), session, user)
            self.assertEqual(updated["scenario"], "edited")
            result = list_part_types("edited", 1, 25, session, user)
            self.assertEqual((result["total"], result["items"][0]["id"]), (1, created["id"]))
            delete_part_type(created["id"], session, user)
            with self.assertRaises(HTTPException) as missing:
                delete_part_type(created["id"], session, user)
            self.assertEqual(missing.exception.status_code, 404)
            with self.assertRaises(HTTPException) as invalid:
                create_part_type(CccScenarioPartTypeIn(part_type_code="   "), session, user)
            self.assertEqual(invalid.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()