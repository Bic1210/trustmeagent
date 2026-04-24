from pathlib import Path

from trust_me.detectors.build_check import detect_build_status
from trust_me.detectors.core_file_risk import detect_core_file_risk
from trust_me.detectors.diff_scope_check import detect_diff_scope
from trust_me.detectors.import_check import detect_missing_import_risk
from trust_me.detectors.lint_check import detect_lint_status
from trust_me.detectors.lockfile_drift_check import detect_lockfile_drift
from trust_me.detectors.review_summary_check import detect_review_summary
from trust_me.detectors.test_check import detect_test_status
from trust_me.detectors.type_check import detect_type_status


def _normalize_detector_result(name: str, finding: dict) -> dict:
    normalized = {
        "detector": finding.get("detector", name),
        "status": finding.get("status", "completed"),
        "evidence": finding.get("evidence", {}),
        "verified": list(finding.get("verified", [])),
        "unverified": list(finding.get("unverified", [])),
        "suspicious": list(finding.get("suspicious", [])),
        "action_items": list(finding.get("action_items", [])),
    }
    return normalized


def _append_detector_result(report: dict, detector: object, finding: dict) -> None:
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
    with_review: bool = False,
) -> dict:
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
    report = {
        "root": str(root),
        "diff_range": diff_range,
        "patch_path": patch_path,
        "detectors": [],
        "verified": [],
        "unverified": [],
        "suspicious": [],
        "action_items": [],
    }
    for detector in detectors:
        finding = detector(root=root, diff_range=diff_range, patch_path=patch_path)
        _append_detector_result(report, detector, finding)
    if with_review:
        review_finding = detect_review_summary(
            root=root,
            report=report,
            diff_range=diff_range,
            patch_path=patch_path,
        )
        _append_detector_result(report, detect_review_summary, review_finding)
    return report
