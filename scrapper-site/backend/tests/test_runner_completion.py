import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.runner import Runner


class RunnerCompletionTests(unittest.TestCase):
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