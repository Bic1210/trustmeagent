from __future__ import annotations

from pathlib import Path
from typing import Any

from trust_me.utils.claude import build_review_prompt, run_claude_json


def _list_of_strings(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def detect_review_summary(root: Path, report: dict[str, Any], diff_range: str | None = None, patch_path: str | None = None) -> dict:
    prompt = build_review_prompt(report)
    code, payload, error = run_claude_json(prompt, cwd=root)
    if code == 127:
        return {
            "detector": "review_summary_check",
            "status": "not_configured",
            "evidence": {"reason": "claude_not_installed"},
            "verified": [],
            "unverified": ["Claude CLI is not installed; review summary unavailable"],
            "suspicious": [],
            "action_items": ["install and authenticate Claude CLI to enable tester-style review summaries"],
        }

    if code != 0 or payload is None:
        return {
            "detector": "review_summary_check",
            "status": "error",
            "evidence": {"reason": "claude_failed", "detail": error},
            "verified": [],
            "unverified": [f"review summary generation failed: {error}"],
            "suspicious": [],
            "action_items": ["verify Claude CLI is authenticated and returns valid JSON"],
        }

    verdict = payload.get("verdict", {})
    trust_level = verdict.get("trust_level") if isinstance(verdict, dict) else None
    trust_reason = verdict.get("reason") if isinstance(verdict, dict) else None

    tested_evidence = _list_of_strings(payload, "tested_evidence")
    untested_areas = _list_of_strings(payload, "untested_areas")
    risk_hypotheses = _list_of_strings(payload, "risk_hypotheses")
    manual_checks = _list_of_strings(payload, "manual_checks")

    verified = [f"review summary captured {len(tested_evidence)} evidence-backed checks"] if tested_evidence else []
    if isinstance(trust_level, str) and isinstance(trust_reason, str) and trust_reason.strip():
        verified.append(f"review verdict: {trust_level} trust - {trust_reason.strip()}")

    return {
        "detector": "review_summary_check",
        "status": "passed",
        "evidence": payload,
        "verified": verified,
        "unverified": untested_areas,
        "suspicious": risk_hypotheses,
        "action_items": manual_checks,
    }
