import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trust_me.harness import run_harness


class HarnessTests(unittest.TestCase):
    @patch("trust_me.harness.detect_core_file_risk")
    @patch("trust_me.harness.detect_lockfile_drift")
    @patch("trust_me.harness.detect_diff_scope")
    @patch("trust_me.harness.detect_missing_import_risk")
    @patch("trust_me.harness.detect_test_status")
    @patch("trust_me.harness.detect_build_status")
    @patch("trust_me.harness.detect_type_status")
    @patch("trust_me.harness.detect_lint_status")
    def test_run_harness_preserves_detector_results_and_aggregates_buckets(
        self,
        mock_lint: object,
        mock_type: object,
        mock_build: object,
        mock_test: object,
        mock_import: object,
        mock_scope: object,
        mock_lockfile: object,
        mock_core: object,
    ) -> None:
        mock_lint.return_value = {
            "detector": "lint_check",
            "status": "passed",
            "evidence": {"exit_code": 0},
            "verified": ["ruff passed"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }
        mock_type.return_value = {
            "unverified": ["type check not wired yet"],
            "verified": [],
            "suspicious": [],
            "action_items": [],
        }
        mock_build.return_value = {
            "verified": ["compileall build smoke check passed"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }
        mock_test.return_value = {"verified": [], "unverified": [], "suspicious": [], "action_items": []}
        mock_import.return_value = {"verified": [], "unverified": [], "suspicious": [], "action_items": []}
        mock_scope.return_value = {"verified": [], "unverified": [], "suspicious": [], "action_items": []}
        mock_lockfile.return_value = {"verified": [], "unverified": [], "suspicious": [], "action_items": []}
        mock_core.return_value = {"verified": [], "unverified": [], "suspicious": [], "action_items": []}

        with tempfile.TemporaryDirectory() as tmp_dir:
            report = run_harness(Path(tmp_dir))

        self.assertEqual(report["verified"], ["ruff passed", "compileall build smoke check passed"])
        self.assertEqual(report["unverified"], ["type check not wired yet"])
        self.assertEqual(len(report["detectors"]), 8)
        self.assertEqual(report["detectors"][0]["detector"], "lint_check")
        self.assertEqual(report["detectors"][0]["status"], "passed")
        self.assertEqual(report["detectors"][0]["evidence"], {"exit_code": 0})
        self.assertEqual(report["detectors"][1]["detector"], "detect_type_status")
        self.assertEqual(report["detectors"][1]["status"], "completed")

    @patch("trust_me.harness.detect_review_summary")
    @patch("trust_me.harness.detect_core_file_risk")
    @patch("trust_me.harness.detect_lockfile_drift")
    @patch("trust_me.harness.detect_diff_scope")
    @patch("trust_me.harness.detect_missing_import_risk")
    @patch("trust_me.harness.detect_test_status")
    @patch("trust_me.harness.detect_build_status")
    @patch("trust_me.harness.detect_type_status")
    @patch("trust_me.harness.detect_lint_status")
    def test_run_harness_optionally_appends_review_summary(
        self,
        mock_lint: object,
        mock_type: object,
        mock_build: object,
        mock_test: object,
        mock_import: object,
        mock_scope: object,
        mock_lockfile: object,
        mock_core: object,
        mock_review: object,
    ) -> None:
        empty = {"verified": [], "unverified": [], "suspicious": [], "action_items": []}
        mock_lint.return_value = empty
        mock_type.return_value = empty
        mock_build.return_value = empty
        mock_test.return_value = empty
        mock_import.return_value = empty
        mock_scope.return_value = empty
        mock_lockfile.return_value = empty
        mock_core.return_value = empty
        mock_review.return_value = {
            "detector": "review_summary_check",
            "status": "passed",
            "evidence": {"change_summary": "summary"},
            "verified": ["review verdict: medium trust - needs checks"],
            "unverified": [],
            "suspicious": ["edge case may regress"],
            "action_items": ["manually verify empty input"],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            report = run_harness(Path(tmp_dir), with_review=True)

        self.assertEqual(report["detectors"][-1]["detector"], "review_summary_check")
        self.assertIn("review verdict: medium trust - needs checks", report["verified"])
        self.assertIn("edge case may regress", report["suspicious"])
        self.assertIn("manually verify empty input", report["action_items"])


if __name__ == "__main__":
    unittest.main()
