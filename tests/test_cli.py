import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from trust_me import cli
from tests.git_helpers import commit_files, init_repo


class CliTests(unittest.TestCase):
    @patch("trust_me.cli.run_harness")
    @patch("trust_me.cli.persist_run_artifacts")
    def test_main_renders_text_report_and_artifact_path(
        self,
        mock_persist_run_artifacts: object,
        mock_run_harness: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            mock_run_harness.return_value = {
                "verified": ["tests passed"],
                "unverified": ["lint unavailable"],
                "suspicious": ["core risk present"],
                "action_items": ["inspect parser.py"],
            }
            mock_persist_run_artifacts.return_value = root / "runs" / "run_2026_04_22_220000"

            with patch("sys.argv", ["trust-me", "run", "--root", str(root)]):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    cli.main()

        output = buffer.getvalue()
        self.assertIn("Patch Confidence Report", output)
        self.assertIn("Confidence:", output)
        self.assertIn("Detector Breakdown", output)
        self.assertIn("Verified", output)
        self.assertIn("- tests passed", output)
        self.assertIn("Artifacts saved to", output)
        mock_run_harness.assert_called_once()
        mock_persist_run_artifacts.assert_called_once()

    @patch("trust_me.cli.run_tui")
    @patch("trust_me.cli.run_harness")
    @patch("trust_me.cli.persist_run_artifacts")
    def test_main_routes_tui_format_into_interactive_renderer(
        self,
        mock_persist_run_artifacts: object,
        mock_run_harness: object,
        mock_run_tui: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report = {
                "verified": ["tests passed"],
                "unverified": [],
                "suspicious": [],
                "action_items": [],
            }
            mock_run_harness.return_value = report
            mock_persist_run_artifacts.return_value = root / "runs" / "run_2026_04_22_220000"

            with patch("sys.argv", ["trust-me", "run", "--root", str(root), "--format", "tui"]):
                cli.main()

        mock_run_tui.assert_called_once_with(report, run_dir=str(root / "runs" / "run_2026_04_22_220000"))

    @patch("trust_me.cli.run_harness")
    @patch("trust_me.cli.persist_run_artifacts")
    def test_main_renders_json_without_artifact_message(
        self,
        mock_persist_run_artifacts: object,
        mock_run_harness: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report = {
                "verified": ["tests passed"],
                "unverified": [],
                "suspicious": [],
                "action_items": [],
            }
            mock_run_harness.return_value = report
            mock_persist_run_artifacts.return_value = root / "runs" / "run_2026_04_22_220000"

            with patch("sys.argv", ["trust-me", "run", "--root", str(root), "--format", "json"]):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    cli.main()

        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload, report)
        self.assertNotIn("Artifacts saved to", buffer.getvalue())
        mock_persist_run_artifacts.assert_called_once()

    @patch("trust_me.cli.persist_run_artifacts")
    @patch("trust_me.cli.run_harness")
    def test_main_respects_no_save_flag(
        self,
        mock_run_harness: object,
        mock_persist_run_artifacts: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            mock_run_harness.return_value = {
                "detectors": [
                    {
                        "detector": "review_summary_check",
                        "status": "passed",
                        "evidence": {
                            "change_summary": "cli output changed",
                            "verdict": {"trust_level": "medium", "reason": "needs manual inspection"},
                        },
                        "verified": [],
                        "unverified": [],
                        "suspicious": [],
                        "action_items": [],
                    }
                ],
                "verified": [],
                "unverified": [],
                "suspicious": [],
                "action_items": [],
            }

            with patch("sys.argv", ["trust-me", "run", "--root", str(root), "--no-save"]):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    cli.main()

        mock_persist_run_artifacts.assert_not_called()
        self.assertNotIn("Artifacts saved to", buffer.getvalue())

    @patch("trust_me.cli.persist_run_artifacts")
    @patch("trust_me.cli.run_harness")
    def test_main_passes_with_review_flag_into_harness(
        self,
        mock_run_harness: object,
        mock_persist_run_artifacts: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            mock_run_harness.return_value = {
                "verified": [],
                "unverified": [],
                "suspicious": [],
                "action_items": [],
            }
            mock_persist_run_artifacts.return_value = root / "runs" / "run_2026_04_22_220000"

            with patch(
                "sys.argv",
                ["trust-me", "run", "--root", str(root), "--with-review", "--patch", "demo.patch"],
            ):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    cli.main()

        _ = buffer.getvalue()
        mock_run_harness.assert_called_once_with(
            root=root.resolve(),
            diff_range=None,
            patch_path="demo.patch",
            with_review=True,
        )
        mock_persist_run_artifacts.assert_called_once()

    @patch("trust_me.cli.persist_run_artifacts")
    @patch("trust_me.cli.run_harness")
    def test_main_renders_review_narrative_in_text_mode(
        self,
        mock_run_harness: object,
        mock_persist_run_artifacts: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            mock_run_harness.return_value = {
                "detectors": [
                    {
                        "detector": "review_summary_check",
                        "status": "passed",
                        "evidence": {
                            "change_summary": "parser behavior changed",
                            "verdict": {"trust_level": "low", "reason": "coverage is incomplete"},
                        },
                        "verified": [],
                        "unverified": [],
                        "suspicious": [],
                        "action_items": [],
                    }
                ],
                "verified": [],
                "unverified": [],
                "suspicious": [],
                "action_items": [],
            }
            mock_persist_run_artifacts.return_value = root / "runs" / "run_2026_04_22_220000"

            with patch("sys.argv", ["trust-me", "run", "--root", str(root)]):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    cli.main()

        output = buffer.getvalue()
        self.assertIn("Review Narrative", output)
        self.assertIn("parser behavior changed", output)
        self.assertIn("verdict: low trust - coverage is incomplete", output)

    def test_main_runs_real_git_diff_range_in_json_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_repo(
                root,
                {
                    "trust_me/parser.py": "VALUE = 1\n",
                    "tests/test_parser.py": "def test_parser():\n    assert True\n",
                },
            )
            commit_files(
                root,
                {
                    "trust_me/parser.py": "VALUE = 2\n",
                    "tests/test_parser.py": "def test_parser():\n    assert 2 == 2\n",
                },
                "update parser",
            )

            with patch(
                "sys.argv",
                ["trust-me", "run", "--root", str(root), "--diff", "HEAD~1", "--format", "json", "--no-save"],
            ):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    cli.main()

        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["diff_range"], "HEAD~1")
        detector_by_name = {detector["detector"]: detector for detector in payload["detectors"]}
        self.assertEqual(detector_by_name["diff_scope_check"]["evidence"]["source"], "git_diff_range")
        self.assertEqual(detector_by_name["core_file_risk"]["evidence"]["source"], "git_diff_range")
        self.assertEqual(detector_by_name["core_file_risk"]["status"], "passed")


if __name__ == "__main__":
    unittest.main()
