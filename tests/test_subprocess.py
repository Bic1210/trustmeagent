import sys
import tempfile
import unittest
from pathlib import Path

from trust_me.utils.subprocess import run_command


class RunCommandTests(unittest.TestCase):
    def test_run_command_captures_stdout_and_stderr(self) -> None:
        code, stdout, stderr = run_command(
            [
                sys.executable,
                "-c",
                "import sys; print('hello'); print('warning', file=sys.stderr)",
            ]
        )

        self.assertEqual(code, 0)
        self.assertEqual(stdout.strip(), "hello")
        self.assertEqual(stderr.strip(), "warning")

    def test_run_command_uses_cwd_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            code, stdout, stderr = run_command(
                [
                    sys.executable,
                    "-c",
                    "import os; print(os.getcwd()); print(os.environ['PATCH_CONFIDENCE_FLAG'])",
                ],
                cwd=Path(tmp_dir),
                env={"PATCH_CONFIDENCE_FLAG": "enabled"},
            )

        self.assertEqual(code, 0)
        self.assertEqual(stdout.splitlines(), [tmp_dir, "enabled"])
        self.assertEqual(stderr, "")

    def test_run_command_reports_missing_command(self) -> None:
        code, stdout, stderr = run_command(["definitely-not-a-real-command"])

        self.assertEqual(code, 127)
        self.assertEqual(stdout, "")
        self.assertIn("command not found", stderr)

    def test_run_command_reports_timeout(self) -> None:
        code, stdout, stderr = run_command(
            [sys.executable, "-c", "import time; time.sleep(0.2)"],
            timeout=0.01,
        )

        self.assertEqual(code, 124)
        self.assertEqual(stdout, "")
        self.assertIn("timed out", stderr)

    def test_run_command_can_limit_captured_output_to_tail(self) -> None:
        code, stdout, stderr = run_command(
            [
                sys.executable,
                "-c",
                "import sys; print('alpha'); print('beta'); print('warn-alpha', file=sys.stderr); print('warn-beta', file=sys.stderr)",
            ],
            max_output_chars=5,
        )

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "beta\n")
        self.assertEqual(stderr, "beta\n")

    def test_run_command_rejects_empty_command(self) -> None:
        with self.assertRaises(ValueError):
            run_command([])


if __name__ == "__main__":
    unittest.main()
