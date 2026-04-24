from __future__ import annotations


def _count(report: dict, key: str) -> int:
    return len(report.get(key, []))


def _confidence_score(report: dict) -> int:
    verified = _count(report, "verified")
    unverified = _count(report, "unverified")
    suspicious = _count(report, "suspicious")
    action_items = _count(report, "action_items")
    score = 100 - (unverified * 12) - (suspicious * 18) - max(0, action_items - verified) * 4
    return max(0, min(100, score))


def _headline(score: int) -> str:
    if score >= 80:
        return "high confidence"
    if score >= 55:
        return "guarded confidence"
    return "low confidence"


def _detector_rows(report: dict) -> list[str]:
    rows: list[str] = []
    for detector in report.get("detectors", []):
        name = str(detector.get("detector", "unknown"))
        status = str(detector.get("status", "completed"))
        duration = detector.get("duration_seconds")
        duration_text = f"{float(duration):>6.3f}s" if isinstance(duration, (int, float)) else "   n/a "
        findings = detector.get("suspicious") or detector.get("unverified") or detector.get("verified") or ["none"]
        primary = str(findings[0])
        rows.append(f"- {name:<22} {status:<15} {duration_text}  {primary}")
    return rows


def _review_block(report: dict) -> list[str]:
    for detector in report.get("detectors", []):
        if detector.get("detector") != "review_summary_check":
            continue
        evidence = detector.get("evidence", {})
        if not isinstance(evidence, dict):
            return []
        summary = evidence.get("change_summary")
        verdict = evidence.get("verdict", {})
        if not isinstance(summary, str) or not summary.strip():
            return []
        lines = ["Review Narrative", f"- {summary.strip()}"]
        if isinstance(verdict, dict):
            trust_level = verdict.get("trust_level")
            trust_reason = verdict.get("reason")
            if isinstance(trust_level, str) and isinstance(trust_reason, str):
                lines.append(f"- verdict: {trust_level} trust - {trust_reason}")
        return lines
    return []


def _timing_block(report: dict) -> list[str]:
    detectors = report.get("detectors", [])
    timed = [
        detector for detector in detectors if isinstance(detector.get("duration_seconds"), (int, float))
    ]
    lines = [f"total: {float(report.get('duration_seconds', 0.0)):.3f}s"]
    if not timed:
        lines.append("detectors: none")
        return lines

    ordered = sorted(timed, key=lambda detector: float(detector.get("duration_seconds", 0.0)), reverse=True)
    lines.extend(
        f"{detector.get('detector', 'unknown')}: {float(detector.get('duration_seconds', 0.0)):.3f}s"
        for detector in ordered[:5]
    )
    return lines


def _section(title: str, items: list[str]) -> list[str]:
    lines = [title]
    if not items:
        lines.append("- none")
    else:
        lines.extend(f"- {item}" for item in items)
    return lines


def render_text(report: dict, run_dir: str | None = None) -> str:
    score = _confidence_score(report)
    lines = [
        "Patch Confidence Report",
        f"Confidence: {score}% ({_headline(score)})",
        f"Root: {report.get('root', '.')}",
        f"Input: diff={report.get('diff_range') or 'working tree'} patch={report.get('patch_path') or 'none'}",
        f"Scope: requested={report.get('requested_scope', 'all')} effective={report.get('effective_scope', 'all')}",
        f"Duration: {float(report.get('duration_seconds', 0.0)):.3f}s",
        f"Counts: verified={_count(report, 'verified')} unverified={_count(report, 'unverified')} suspicious={_count(report, 'suspicious')} action_items={_count(report, 'action_items')}",
        "",
        "Detector Breakdown",
    ]

    detector_rows = _detector_rows(report)
    if detector_rows:
        lines.extend(detector_rows)
    else:
        lines.append("- no detector output")

    lines.extend(["", *_section("Timing", _timing_block(report))])

    scope_notes = report.get("scope_notes", [])
    if scope_notes:
        lines.extend(["", *_section("Scope Notes", scope_notes)])

    review_lines = _review_block(report)
    if review_lines:
        lines.extend(["", *review_lines])

    lines.extend(
        [
            "",
            *_section("Verified", report.get("verified", [])),
            "",
            *_section("Unverified", report.get("unverified", [])),
            "",
            *_section("Suspicious", report.get("suspicious", [])),
            "",
            *_section("Action Items", report.get("action_items", [])),
        ]
    )

    if run_dir is not None:
        lines.extend(["", f"Artifacts saved to {run_dir}"])

    return "\n".join(lines) + "\n"
