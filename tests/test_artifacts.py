import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any

from trust_me.artifacts import persist_run_artifacts


class ArtifactPersistenceTests(unittest.TestCase):
    def test_persist_run_artifacts_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report: dict[str, Any] = {
                "root": str(root),
                "diff_range": None,
                "patch_path": None,
                "detectors": [
                    {
                        "detector": "test_check",
                        "status": "passed",
                        "evidence": {"exit_code": 0},
                        "verified": ["2 tests passed"],
                        "unverified": [],
                        "suspicious": [],
                        "action_items": [],
                    }
                ],
                "verified": ["2 tests passed"],
                "unverified": [],
                "suspicious": [],
                "action_items": [],
            }

            run_dir = persist_run_artifacts(
                root,
                report,
                diff_range=None,
                patch_path=None,
                scope="all",
                with_review=False,
                argv=["python3", "-m", "trust_me.cli", "run"],
                timestamp=datetime(2026, 4, 22, 17, 30, 0),
            )

            self.assertEqual(run_dir.name, "run_2026_04_22_173000")
            expected_files = {
                "summary.json",
                "report.json",
                "findings.jsonl",
                "report.html",
                "commands.json",
                "raw_diff.patch",
            }
            self.assertEqual({path.name for path in run_dir.iterdir()}, expected_files)

            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["requested_scope"], "all")
            self.assertEqual(summary["effective_scope"], "all")
            self.assertEqual(summary["detector_count"], 1)
            self.assertEqual(summary["verified_count"], 1)

            findings = (run_dir / "findings.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(findings), 1)
            self.assertEqual(json.loads(findings[0])["detector"], "test_check")

            commands = json.loads((run_dir / "commands.json").read_text(encoding="utf-8"))
            self.assertEqual(commands["argv"], ["python3", "-m", "trust_me.cli", "run"])

            report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
            self.assertIn("timing", report_json)
            self.assertEqual(report_json["timing"]["detectors"][0]["detector"], "test_check")

    def test_persist_run_artifacts_avoids_timestamp_directory_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report: dict[str, Any] = {
                "root": str(root),
                "diff_range": None,
                "patch_path": None,
                "detectors": [],
                "verified": [],
                "unverified": [],
                "suspicious": [],
                "action_items": [],
            }
            timestamp = datetime(2026, 4, 22, 17, 30, 0)

            first = persist_run_artifacts(
                root,
                report,
                diff_range=None,
                patch_path=None,
                scope="all",
                with_review=False,
                argv=["python3", "-m", "trust_me.cli", "run"],
                timestamp=timestamp,
            )
            second = persist_run_artifacts(
                root,
                report,
                diff_range=None,
                patch_path=None,
                scope="all",
                with_review=False,
                argv=["python3", "-m", "trust_me.cli", "run"],
                timestamp=timestamp,
            )

            self.assertEqual(first.name, "run_2026_04_22_173000")
            self.assertEqual(second.name, "run_2026_04_22_173000_01")


if __name__ == "__main__":
    unittest.main()
