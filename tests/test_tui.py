import unittest

from trust_me.render.tui import build_tui_lines


class TuiRenderTests(unittest.TestCase):
    def test_build_tui_lines_contains_sections_and_artifact_path(self) -> None:
        report = {
            "root": "/tmp/demo",
            "diff_range": "HEAD~1",
            "patch_path": None,
            "detectors": [
                {
                    "detector": "diff_scope_check",
                    "status": "passed",
                    "verified": ["scope measured"],
                    "unverified": [],
                    "suspicious": [],
                    "action_items": [],
                    "evidence": {},
                }
            ],
            "verified": ["tests passed"],
            "unverified": ["lint unavailable"],
            "suspicious": ["core risk present"],
            "action_items": ["inspect parser.py"],
        }

        lines = build_tui_lines(report, run_dir="/tmp/demo/runs/run_1")
        payload = "\n".join(lines)

        self.assertIn("Patch Confidence TUI", payload)
        self.assertIn("Detector Breakdown", payload)
        self.assertIn("Verified", payload)
        self.assertIn("Unverified", payload)
        self.assertIn("Suspicious", payload)
        self.assertIn("Action Items", payload)
        self.assertIn("Artifacts saved to /tmp/demo/runs/run_1", payload)


if __name__ == "__main__":
    unittest.main()
