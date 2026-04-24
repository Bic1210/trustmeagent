from pathlib import Path
from time import perf_counter
from typing import Any

from trust_me.detectors.build_check import detect_build_status
from trust_me.detectors.core_file_risk import detect_core_file_risk
from trust_me.detectors.diff_scope_check import detect_diff_scope
from trust_me.detectors.import_check import detect_missing_import_risk
from trust_me.detectors.lint_check import detect_lint_status
from trust_me.detectors.lockfile_drift_check import detect_lockfile_drift
from trust_me.detectors.review_summary_check import detect_review_summary
from trust_me.detectors.test_check import detect_test_status
from trust_me.detectors.type_check import detect_type_status
from trust_me.utils.diff import load_changed_files


def _normalize_detector_result(name: str, finding: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "detector": finding.get("detector", name),
        "status": finding.get("status", "completed"),
        "duration_seconds": finding.get("duration_seconds"),
        "evidence": finding.get("evidence", {}),
        "verified": list(finding.get("verified", [])),
        "unverified": list(finding.get("unverified", [])),
        "suspicious": list(finding.get("suspicious", [])),
        "action_items": list(finding.get("action_items", [])),
    }
    return normalized


def _append_detector_result(report: dict[str, Any], detector: object, finding: dict[str, Any]) -> None:
    detector_name = (
        finding.get("detector")
        or getattr(detector, "__name__", None)
        or getattr(detector, "_mock_name", None)
        or "unknown_detector"
    )
    normalized = _normalize_detector_result(detector_name, finding)
    report["detectors"].append(normalized)
    for key in ("verified", "unverified", "suspicious", "action_items"):
        report[key].extend(normalized[key])


def run_harness(
    root: Path,
    diff_range: str | None = None,
    patch_path: str | None = None,
    scope: str = "all",
    with_review: bool = False,
) -> dict:
    started = perf_counter()
    detectors = [
        detect_lint_status,
        detect_type_status,
        detect_build_status,
        detect_test_status,
        detect_missing_import_risk,
        detect_diff_scope,
        detect_lockfile_drift,
        detect_core_file_risk,
    ]
    effective_scope = scope
    changed_files: list[str] | None = None
    scope_notes: list[str] = []
    changed_scope_meta: dict[str, Any] = {}
    if scope == "changed":
        changed_files, changed_source, changed_error, changed_notes, changed_scope_parsed = load_changed_files(root, patch_path, diff_range)
        if changed_error:
            effective_scope = "all"
            scope_notes.append(f"changed scope unavailable: {changed_error}; falling back to full-project checks")
        else:
            scope_notes.extend(changed_notes)
            changed_scope_meta = {
                "source": changed_source,
                "changed_file_count": len(changed_files or []),
            }
            if changed_scope_parsed is not None:
                changed_scope_meta.update(
                    {
                        "hunk_count": changed_scope_parsed["hunk_count"],
                        "added_lines": changed_scope_parsed["added_lines"],
                        "removed_lines": changed_scope_parsed["removed_lines"],
                    }
                )
    report: dict[str, Any] = {
        "root": str(root),
        "diff_range": diff_range,
        "patch_path": patch_path,
        "requested_scope": scope,
        "effective_scope": effective_scope,
        "scope_notes": scope_notes,
        "changed_scope": changed_scope_meta,
        "detectors": [],
        "verified": [],
        "unverified": [],
        "suspicious": [],
        "action_items": [],
    }
    for detector in detectors:
        detector_started = perf_counter()
        finding = detector(
            root=root,
            diff_range=diff_range,
            patch_path=patch_path,
            scope=effective_scope,
            changed_files=changed_files,
        )
        finding["duration_seconds"] = round(perf_counter() - detector_started, 3)
        _append_detector_result(report, detector, finding)
    if with_review:
        detector_started = perf_counter()
        review_finding = detect_review_summary(
            root=root,
            report=report,
            diff_range=diff_range,
            patch_path=patch_path,
            scope=effective_scope,
            changed_files=changed_files,
        )
        review_finding["duration_seconds"] = round(perf_counter() - detector_started, 3)
        _append_detector_result(report, detect_review_summary, review_finding)
    report["duration_seconds"] = round(perf_counter() - started, 3)
    return report
