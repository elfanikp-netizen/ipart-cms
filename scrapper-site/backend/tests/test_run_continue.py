import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.crawlers import CRAWLERS
from app.routers.runs import continue_run


class ContinueRunTests(unittest.TestCase):
    def test_registered_crawlers_can_continue_without_an_initial_output_file(self) -> None:
        self.assertTrue(CRAWLERS)
        for crawler_id, spec in CRAWLERS.items():
            with self.subTest(crawler=crawler_id):
                self.assertTrue(spec.supports_resume)
                self.assertFalse(spec.resume_requires_output)

    def test_keystone_can_continue_without_an_output_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            input_path = run_dir / "input.xlsx"
            input_path.touch()
            run = SimpleNamespace(
                id=75,
                status="stopped",
                crawler_id="keystone",
                params=json.dumps({"column": "PARTSLINK"}),
                input_path=str(input_path),
                output_path=str(run_dir / "output.xlsx"),
                error=None,
                returncode=1,
                pid=None,
                waiting_for_human=False,
                finished_at="finished",
            )
            user = SimpleNamespace(id=4, role="user")
            database = MagicMock()
            database.get.return_value = run
            spec = SimpleNamespace(
                supports_resume=True,
                resume_requires_output=False,
                resolve_script=lambda _site: Path(__file__),
                python=Path(sys.executable),
            )

            with patch("app.routers.runs.require_run_owner_or_admin"), patch(
                "app.routers.runs.get_crawler", return_value=spec
            ), patch("app.routers.runs.runner.active_run_ids", return_value=[]), patch(
                "app.routers.runs.runner.enqueue"
            ) as enqueue, patch("app.routers.runs.log_activity"), patch(
                "app.routers.runs.to_out", return_value={"id": 75}
            ):
                result = continue_run(75, database, user)

            self.assertEqual(result, {"id": 75})
            self.assertEqual(run.status, "queued")
            self.assertEqual(json.loads(run.params)["resume"], False)
            enqueue.assert_called_once_with(75)
            database.commit.assert_called_once()

    def test_keystone_still_rejects_a_corrupt_existing_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            input_path = run_dir / "input.xlsx"
            input_path.touch()
            output_path = run_dir / "output.xlsx"
            output_path.write_text("not an Excel workbook", encoding="utf-8")
            run = SimpleNamespace(
                id=75,
                status="failed",
                crawler_id="keystone",
                params="{}",
                input_path=str(input_path),
                output_path=str(output_path),
            )
            database = MagicMock()
            database.get.return_value = run
            spec = SimpleNamespace(
                supports_resume=True,
                resume_requires_output=False,
                resolve_script=lambda _site: Path(__file__),
                python=Path(sys.executable),
            )

            with patch("app.routers.runs.require_run_owner_or_admin"), patch(
                "app.routers.runs.get_crawler", return_value=spec
            ), patch("app.routers.runs.runner.active_run_ids", return_value=[]):
                with self.assertRaises(HTTPException) as raised:
                    continue_run(75, database, SimpleNamespace(id=4, role="user"))

            self.assertEqual(raised.exception.status_code, 409)
            self.assertIn("not a valid Excel workbook", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()