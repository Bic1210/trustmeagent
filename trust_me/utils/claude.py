from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trust_me.utils.subprocess import run_command


def _truncate_text(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


def _extract_json_text(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def run_claude_json(prompt: str, cwd: Path | None = None, timeout: float = 120.0) -> tuple[int, dict[str, Any] | None, str]:
    code, stdout, stderr = run_command(["claude", "--print", prompt], cwd=cwd, timeout=timeout)
    if code != 0:
        detail = stderr.strip() or stdout.strip() or "claude command failed"
        return code, None, detail

    raw = _extract_json_text(stdout)
    if not raw:
        return 1, None, "claude returned empty output"

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return 1, None, f"claude returned invalid JSON: {exc.msg}"

    if not isinstance(payload, dict):
        return 1, None, "claude returned non-object JSON"

    return 0, payload, ""


def build_review_prompt(report: dict[str, Any]) -> str:
    report_json = json.dumps(report, ensure_ascii=False, indent=2)
    return (
        "You are producing a tester-grade review artifact for a code patch harness.\n"
        "Respond with JSON only. Do not include markdown.\n"
        "Use this exact schema:\n"
        "{\n"
        '  "change_summary": "string",\n'
        '  "risk_hypotheses": ["string"],\n'
        '  "tested_evidence": ["string"],\n'
        '  "untested_areas": ["string"],\n'
        '  "manual_checks": ["string"],\n'
        '  "verdict": {\n'
        '    "trust_level": "low|medium|high",\n'
        '    "reason": "string"\n'
        "  }\n"
        "}\n"
        "Requirements:\n"
        "- Ground claims in the supplied detector evidence.\n"
        "- Be explicit about uncertainty.\n"
        "- Do not invent tests that did not run.\n"
        "- Keep each list short and concrete.\n"
        "Input report:\n"
        f"{_truncate_text(report_json)}"
    )
