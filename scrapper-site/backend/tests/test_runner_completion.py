import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.runner import Runner


class RunnerCompletionTests(unittest.TestCase):
    def test_successful_exit_persists_success_status_and_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            output_path = run_dir / "output.xlsx"
            output_path.touch()
            run = SimpleNamespace(
                id=1,
                status="queued",
                crawler_id="ccc",
                params="{}",
                input_path=str(run_dir / "input.xlsx"),
                output_path=str(output_path),
                log_path=str(run_dir / "run.log"),
                user_id=1,
                started_at=None,
                finished_at=None,
                waiting_for_human=False,
                progress_total=None,
                progress_done=None,
                returncode=None,
                pid=None,
                error=None,
            )
            databases = [MagicMock() for _ in range(3)]
            contexts = []
            for database in databases:
                database.get.return_value = run
                context = MagicMock()
                context.__enter__.return_value = database
                contexts.append(context)
            spec = SimpleNamespace(
                id="ccc",
                python=Path(sys.executable),
                build_args=lambda *_args: ["crawler.py"],
                supports_live_visibility=False,
            )
            process = SimpleNamespace(pid=1234)
            runner = Runner()

            with patch("app.runner.SessionLocal", side_effect=contexts), patch(
                "app.runner.get_crawler", return_value=spec
            ), patch.object(
                runner, "_prepare_run_workspace", return_value=(Path("crawler.py"), run_dir, {})
            ), patch("app.runner.subprocess.Popen", return_value=process), patch.object(
                runner, "_monitor_process_output", return_value=0
            ):
                runner._execute(run.id, 20000)

            self.assertEqual(run.status, "success")
            self.assertEqual(run.returncode, 0)
            self.assertIsNotNone(run.finished_at)
            databases[2].add.assert_called_once()
            databases[2].commit.assert_called_once()

    def test_crawler_exit_is_not_blocked_by_child_holding_log_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            log_path = run_dir / "run.log"
            child_pid_path = run_dir / "child.pid"
            child_code = textwrap.dedent(
                f"""\
                import os
                import time
                open({str(child_pid_path)!r}, "w").write(str(os.getpid()))
                time.sleep(30)
                """
            )
            crawler_code = textwrap.dedent(
                f"""\
                import subprocess
                import sys
                import time
                subprocess.Popen([sys.executable, "-c", {child_code!r}])
                deadline = time.monotonic() + 5
                while not __import__("os").path.exists({str(child_pid_path)!r}) and time.monotonic() < deadline:
                    time.sleep(0.01)
                print("Progress: 1/2")
                """
            )
            runner = Runner()
            with patch.object(runner, "_set_progress") as set_progress, patch.object(
                runner, "_set_waiting"
            ):
                with log_path.open("w", encoding="utf-8") as log:
                    process = subprocess.Popen(
                        [sys.executable, "-c", crawler_code],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )

                started = time.monotonic()
                try:
                    returncode = runner._monitor_process_output(process, log_path, 1)
                    elapsed = time.monotonic() - started

                    self.assertEqual(returncode, 0)
                    self.assertLess(elapsed, 5)
                    set_progress.assert_called_once_with(1, 1, 2)
                finally:
                    if child_pid_path.exists():
                        child_pid = int(child_pid_path.read_text(encoding="utf-8"))
                        try:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", str(child_pid)],
                                capture_output=True,
                                timeout=5,
                                check=False,
                            )
                        except (OSError, subprocess.SubprocessError):
                            pass


if __name__ == "__main__":
    unittest.main()