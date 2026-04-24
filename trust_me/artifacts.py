from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from trust_me.render.html_report import render_html
from trust_me.render.json_report import render_json
from trust_me.utils.diff import load_patch_text
from trust_me.utils.paths import make_run_dir


def _summary(report: dict[str, Any], with_review: bool) -> dict[str, Any]:
    detectors = report.get("detectors", [])
    return {
        "root": report.get("root"),
        "diff_range": report.get("diff_range"),
        "patch_path": report.get("patch_path"),
        "with_review": with_review,
        "detector_count": len(detectors),
        "verified_count": len(report.get("verified", [])),
        "unverified_count": len(report.get("unverified", [])),
        "suspicious_count": len(report.get("suspicious", [])),
        "action_item_count": len(report.get("action_items", [])),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_findings_jsonl(path: Path, report: dict[str, Any]) -> None:
    detectors = report.get("detectors", [])
    lines = [json.dumps(detector, ensure_ascii=False) for detector in detectors]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def persist_run_artifacts(
    root: Path,
    report: dict[str, Any],
    *,
    diff_range: str | None,
    patch_path: str | None,
    with_review: bool,
    argv: list[str] | None = None,
    timestamp: datetime | None = None,
) -> Path:
    run_dir = make_run_dir(root, timestamp=timestamp)

    summary = _summary(report, with_review=with_review)
    _write_json(run_dir / "summary.json", summary)
    (run_dir / "report.json").write_text(render_json(report), encoding="utf-8")
    _write_findings_jsonl(run_dir / "findings.jsonl", report)
    (run_dir / "report.html").write_text(render_html(report), encoding="utf-8")

    commands = {
        "argv": argv or sys.argv,
        "root": str(root),
        "diff_range": diff_range,
        "patch_path": patch_path,
        "with_review": with_review,
    }
    _write_json(run_dir / "commands.json", commands)

    diff_text, _source, error, _notes = load_patch_text(root, patch_path, diff_range)
    if diff_text is not None:
        (run_dir / "raw_diff.patch").write_text(diff_text, encoding="utf-8")
    elif error:
        (run_dir / "raw_diff.patch").write_text(f"# unavailable: {error}\n", encoding="utf-8")

    return run_dir
