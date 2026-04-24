from __future__ import annotations

from pathlib import Path

from trust_me.utils.diff import load_patch_text, parse_diff_scope


def detect_diff_scope(
    root: Path,
    diff_range: str | None = None,
    patch_path: str | None = None,
    scope: str = "all",
    changed_files: list[str] | None = None,
) -> dict:
    _ = scope, changed_files
    diff_text, source, error, notes = load_patch_text(root, patch_path, diff_range)
    if error:
        return {
            "detector": "diff_scope_check",
            "status": "not_configured" if error == "not a git repository" and patch_path is None and diff_range is None else "error",
            "evidence": {"source": source, "reason": error},
            "verified": [],
            "unverified": [f"diff scope unavailable: {error}"],
            "suspicious": [],
            "action_items": ["provide --patch or initialize a git repository"] if error == "not a git repository" else ["verify the diff input can be read"],
        }

    if diff_text is None:
        return {
            "detector": "diff_scope_check",
            "status": "error",
            "evidence": {"source": source, "reason": "missing_diff_text"},
            "verified": [],
            "unverified": ["diff scope unavailable: missing diff text"],
            "suspicious": [],
            "action_items": ["verify the diff input can be read"],
        }

    parsed = parse_diff_scope(diff_text)
    evidence = {
        "source": source,
        "notes": notes,
        **parsed,
    }

    if parsed["file_count"] == 0:
        return {
            "detector": "diff_scope_check",
            "status": "passed",
            "evidence": evidence,
            "verified": [f"no changed tracked files detected from {source}"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }

    verified = [
        f"diff scope measured: {parsed['file_count']} files, {parsed['hunk_count']} hunks, +{parsed['added_lines']}/-{parsed['removed_lines']} lines"
    ]
    verified.extend(notes)

    suspicious: list[str] = []
    action_items: list[str] = []
    if parsed["file_count"] >= 10:
        suspicious.append(f"diff touches {parsed['file_count']} files")
    if parsed["hunk_count"] >= 20:
        suspicious.append(f"diff spans {parsed['hunk_count']} hunks")
    if parsed["binary_files"] > 0:
        suspicious.append(f"diff includes {parsed['binary_files']} binary files")
        action_items.append("review binary file changes manually")

    if parsed["file_count"] > 0:
        action_items.append(f"inspect changed files: {', '.join(parsed['changed_files'][:5])}")

    return {
        "detector": "diff_scope_check",
        "status": "passed",
        "evidence": evidence,
        "verified": verified,
        "unverified": [],
        "suspicious": suspicious,
        "action_items": action_items,
    }
