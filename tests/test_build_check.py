import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trust_me.detectors.build_check import detect_build_status


class BuildDetectorTests(unittest.TestCase):
    def test_detect_build_status_skips_when_no_supported_target_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_build_status(Path(tmp_dir))

        self.assertEqual(result["detector"], "build_check")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["unverified"], ["no supported build target detected for build_check"])

    @patch("trust_me.detectors.build_check.run_command", return_value=(0, "", ""))
    def test_detect_build_status_uses_compileall_for_python_projects(self, mock_run_command: object) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

            result = detect_build_status(root)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["tool"], "compileall")
        self.assertEqual(result["verified"], ["compileall build smoke check passed"])
        mock_run_command.assert_called_once()

    @patch("trust_me.detectors.build_check.shutil.which", side_effect=lambda name: "/usr/bin/tsc" if name == "tsc" else None)
    @patch("trust_me.detectors.build_check.run_command", return_value=(1, "", "src/index.ts:1: error TS2304\n"))
    def test_detect_build_status_reports_tsc_failures(
        self,
        _mock_run_command: object,
        _mock_which: object,
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
        mock_which: object,
        mock_run_command: object,
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
