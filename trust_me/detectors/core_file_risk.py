from __future__ import annotations

from pathlib import Path

from trust_me.utils.diff import load_patch_text, parse_diff_scope

RISKY_STEMS = {
    "__init__",
    "api",
    "app",
    "auth",
    "cli",
    "config",
    "main",
    "parser",
    "routes",
    "server",
    "settings",
}
RISKY_PARTS = {
    "api",
    "auth",
    "config",
    "core",
    "database",
    "db",
    "models",
    "parser",
    "routes",
    "service",
    "services",
    "settings",
}


def _is_test_file(path: str) -> bool:
    pure = Path(path)
    name = pure.name
    return (
        "tests" in pure.parts
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.js")
        or name.endswith(".test.ts")
        or name.endswith(".test.js")
    )


def _is_risky_file(path: str) -> bool:
    pure = Path(path)
    if _is_test_file(path):
        return False
    if pure.stem in RISKY_STEMS:
        return True
    if any(part in RISKY_PARTS for part in pure.parts):
        return True
    if len(pure.parts) == 1 and pure.suffix in {".py", ".js", ".ts"}:
        return True
    return False


def detect_core_file_risk(root: Path, diff_range: str | None = None, patch_path: str | None = None) -> dict:
    diff_text, source, error, notes = load_patch_text(root, patch_path, diff_range)
    if error:
        return {
            "detector": "core_file_risk",
            "status": "not_configured" if error == "not a git repository" and patch_path is None and diff_range is None else "error",
            "evidence": {"source": source, "reason": error},
            "verified": [],
            "unverified": [f"core file risk unavailable: {error}"],
            "suspicious": [],
            "action_items": ["provide --patch or initialize a git repository"] if error == "not a git repository" else ["verify the diff input can be read"],
        }

    if diff_text is None:
        return {
            "detector": "core_file_risk",
            "status": "error",
            "evidence": {"source": source, "reason": "missing_diff_text"},
            "verified": [],
            "unverified": ["core file risk unavailable: missing diff text"],
            "suspicious": [],
            "action_items": ["verify the diff input can be read"],
        }

    parsed = parse_diff_scope(diff_text)
    changed_files = parsed["changed_files"]
    risky_files = [path for path in changed_files if _is_risky_file(path)]
    changed_test_files = [path for path in changed_files if _is_test_file(path)]
    evidence = {
        "source": source,
        "notes": notes,
        "changed_files": changed_files,
        "risky_files": risky_files,
        "changed_test_files": changed_test_files,
        "risky_file_count": len(risky_files),
        "changed_test_file_count": len(changed_test_files),
    }

    if not changed_files:
        return {
            "detector": "core_file_risk",
            "status": "passed",
            "evidence": evidence,
            "verified": [f"no changed tracked files detected from {source}"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }

    if not risky_files:
        return {
            "detector": "core_file_risk",
            "status": "passed",
            "evidence": evidence,
            "verified": ["no risky core files detected in the current diff scope"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }

    if changed_test_files:
        return {
            "detector": "core_file_risk",
            "status": "passed",
            "evidence": evidence,
            "verified": [f"{len(risky_files)} risky files changed alongside {len(changed_test_files)} test files"],
            "unverified": [],
            "suspicious": [],
            "action_items": [f"inspect risky files: {', '.join(risky_files[:5])}"],
        }

    return {
        "detector": "core_file_risk",
        "status": "failed",
        "evidence": evidence,
        "verified": [],
        "unverified": [],
        "suspicious": [f"{len(risky_files)} risky files changed without any nearby test file updates"],
        "action_items": [
            f"inspect risky files: {', '.join(risky_files[:5])}",
            "add or update tests that exercise the changed core paths",
        ],
    }
