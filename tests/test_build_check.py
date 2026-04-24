import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from trust_me.detectors.build_check import detect_build_status


class BuildDetectorTests(unittest.TestCase):
    def test_detect_build_status_skips_when_no_supported_target_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_build_status(Path(tmp_dir))

        self.assertEqual(result["detector"], "build_check")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["unverified"], ["no supported build target detected for build_check"])

    @patch("trust_me.detectors.build_check.run_command", return_value=(0, "", ""))
    def test_detect_build_status_uses_compileall_for_python_projects(self, mock_run_command: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

            result = detect_build_status(root)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["tool"], "compileall")
        self.assertEqual(result["verified"], ["compileall build smoke check passed"])
        mock_run_command.assert_called_once()

    @patch("trust_me.detectors.build_check.run_command", return_value=(0, "", ""))
    def test_detect_build_status_excludes_virtualenv_from_compileall_targets(self, mock_run_command: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "ignored.py").write_text("print('ignore')\n", encoding="utf-8")

            _ = detect_build_status(root)

        command = mock_run_command.call_args.args[0]
        self.assertEqual(command[:2], [sys.executable, "-m"])
        self.assertEqual(command[2], "compileall")
        self.assertIn(str(root / "app.py"), command)
        self.assertNotIn(str(root), command)
        self.assertNotIn(str(root / ".venv"), command)

    @patch("trust_me.detectors.build_check.run_command", return_value=(0, "", ""))
    def test_detect_build_status_limits_compileall_targets_in_changed_scope(self, mock_run_command: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "worker.py").write_text("print('changed')\n", encoding="utf-8")

            result = detect_build_status(root, scope="changed", changed_files=["worker.py"])

        self.assertEqual(result["status"], "passed")
        command = mock_run_command.call_args.args[0]
        self.assertIn(str(root / "worker.py"), command)
        self.assertNotIn(str(root / "app.py"), command)

    def test_detect_build_status_skips_when_no_changed_supported_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("docs\n", encoding="utf-8")

            result = detect_build_status(root, scope="changed", changed_files=["README.md"])

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["evidence"]["reason"], "no_changed_supported_build_target")

    @patch("trust_me.detectors.build_check.shutil.which", side_effect=lambda name: "/usr/bin/tsc" if name == "tsc" else None)
    @patch("trust_me.detectors.build_check.run_command", return_value=(1, "", "src/index.ts:1: error TS2304\n"))
    def test_detect_build_status_reports_tsc_failures(
        self,
        _mock_run_command: MagicMock,
        _mock_which: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "tsconfig.json").write_text("{}", encoding="utf-8")

            result = detect_build_status(root)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["evidence"]["tool"], "tsc")
        self.assertEqual(result["suspicious"], ["tsc build smoke check failed"])
        self.assertIn("TS2304", result["action_items"][0])

    @patch("trust_me.detectors.build_check.run_command", return_value=(0, "", ""))
    @patch("trust_me.detectors.build_check.shutil.which", side_effect=lambda name: "/usr/bin/go" if name == "go" else None)
    def test_detect_build_status_sets_writable_go_cache_env(
        self,
        mock_which: MagicMock,
        mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "go.mod").write_text("module demo\n\ngo 1.22\n", encoding="utf-8")

            result = detect_build_status(root)

        self.assertEqual(result["status"], "passed")
        _ = mock_which
        self.assertEqual(result["evidence"]["tool"], "go")
        self.assertEqual(result["evidence"]["env_keys"], ["GOCACHE", "GOPATH"])
        self.assertEqual(mock_run_command.call_args.kwargs["env"].keys(), {"GOCACHE", "GOPATH"})


if __name__ == "__main__":
    unittest.main()
