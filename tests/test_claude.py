import unittest
from pathlib import Path
from unittest.mock import patch

from trust_me.detectors.review_summary_check import detect_review_summary
from trust_me.utils.claude import build_review_prompt, run_claude_json


class ClaudeUtilsTests(unittest.TestCase):
    @patch("trust_me.utils.claude.run_command", return_value=(0, '{"ok": true}', ""))
    def test_run_claude_json_parses_object_output(self, _mock_run_command: object) -> None:
        code, payload, error = run_claude_json("prompt", cwd=Path("."))

        self.assertEqual(code, 0)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(error, "")

    @patch("trust_me.utils.claude.run_command", return_value=(0, '```json\n{"ok": true}\n```', ""))
    def test_run_claude_json_parses_fenced_json_output(self, _mock_run_command: object) -> None:
        code, payload, error = run_claude_json("prompt", cwd=Path("."))

        self.assertEqual(code, 0)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(error, "")

    @patch("trust_me.utils.claude.run_command", return_value=(0, '[]', ""))
    def test_run_claude_json_rejects_non_object_json(self, _mock_run_command: object) -> None:
        code, payload, error = run_claude_json("prompt", cwd=Path("."))

        self.assertEqual(code, 1)
        self.assertIsNone(payload)
        self.assertIn("non-object", error)

    def test_build_review_prompt_includes_schema_and_report(self) -> None:
        prompt = build_review_prompt({"verified": ["tests passed"]})

        self.assertIn('"change_summary": "string"', prompt)
        self.assertIn('"trust_level": "low|medium|high"', prompt)
        self.assertIn('"verified": [', prompt)


class ReviewSummaryDetectorTests(unittest.TestCase):
    @patch("trust_me.detectors.review_summary_check.run_claude_json", return_value=(127, None, "command not found: claude"))
    def test_detect_review_summary_reports_missing_claude(self, _mock_run_claude_json: object) -> None:
        result = detect_review_summary(Path("."), report={"verified": []})

        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["unverified"], ["Claude CLI is not installed; review summary unavailable"])

    @patch(
        "trust_me.detectors.review_summary_check.run_claude_json",
        return_value=(
            0,
            {
                "change_summary": "parser behavior changed",
                "risk_hypotheses": ["edge case may regress"],
                "tested_evidence": ["unit tests passed"],
                "untested_areas": ["no large-input coverage"],
                "manual_checks": ["verify empty input manually"],
                "verdict": {"trust_level": "medium", "reason": "deterministic checks are incomplete"},
            },
            "",
        ),
    )
    def test_detect_review_summary_maps_claude_payload_into_report_buckets(self, _mock_run_claude_json: object) -> None:
        result = detect_review_summary(Path("."), report={"verified": ["tests passed"]})

        self.assertEqual(result["status"], "passed")
        self.assertIn("review summary captured 1 evidence-backed checks", result["verified"])
        self.assertIn("review verdict: medium trust - deterministic checks are incomplete", result["verified"])
        self.assertEqual(result["unverified"], ["no large-input coverage"])
        self.assertEqual(result["suspicious"], ["edge case may regress"])
        self.assertEqual(result["action_items"], ["verify empty input manually"])


if __name__ == "__main__":
    unittest.main()
