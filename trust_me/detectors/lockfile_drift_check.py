from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from trust_me.utils.diff import load_patch_text, parse_diff_scope


class ManifestRule(TypedDict):
    label: str
    lockfiles: list[str]


MANIFEST_RULES: dict[str, ManifestRule] = {
    "package.json": {
        "label": "JavaScript dependencies",
        "lockfiles": ["package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb"],
    },
    "pyproject.toml": {
        "label": "Python dependencies",
        "lockfiles": ["uv.lock", "poetry.lock", "pdm.lock"],
    },
    "Cargo.toml": {
        "label": "Rust dependencies",
        "lockfiles": ["Cargo.lock"],
    },
    "go.mod": {
        "label": "Go module dependencies",
        "lockfiles": ["go.sum"],
    },
    "Gemfile": {
        "label": "Ruby dependencies",
        "lockfiles": ["Gemfile.lock"],
    },
    "composer.json": {
        "label": "PHP dependencies",
        "lockfiles": ["composer.lock"],
    },
}


def _candidate_lockfiles(relative_path: str, lockfile_names: list[str]) -> list[str]:
    parent = Path(relative_path).parent
    if str(parent) == ".":
        return lockfile_names
    return [str(parent / name) for name in lockfile_names]


def detect_lockfile_drift(
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
            "detector": "lockfile_drift_check",
            "status": "not_configured" if error == "not a git repository" and patch_path is None and diff_range is None else "error",
            "evidence": {"source": source, "reason": error},
            "verified": [],
            "unverified": [f"lockfile drift unavailable: {error}"],
            "suspicious": [],
            "action_items": ["provide --patch or initialize a git repository"] if error == "not a git repository" else ["verify the diff input can be read"],
        }

    if diff_text is None:
        return {
            "detector": "lockfile_drift_check",
            "status": "error",
            "evidence": {"source": source, "reason": "missing_diff_text"},
            "verified": [],
            "unverified": ["lockfile drift unavailable: missing diff text"],
            "suspicious": [],
            "action_items": ["verify the diff input can be read"],
        }

    parsed = parse_diff_scope(diff_text)
    changed_file_set = set(parsed["changed_files"])

    verified: list[str] = []
    unverified: list[str] = []
    suspicious: list[str] = []
    action_items: list[str] = []
    manifest_checks: list[dict[str, object]] = []

    for changed_file in sorted(changed_file_set):
        manifest_name = Path(changed_file).name
        rule = MANIFEST_RULES.get(manifest_name)
        if rule is None:
            continue

        lockfiles = _candidate_lockfiles(changed_file, list(rule["lockfiles"]))
        changed_lockfiles = [lockfile for lockfile in lockfiles if lockfile in changed_file_set]
        existing_lockfiles = [lockfile for lockfile in lockfiles if (root / lockfile).exists()]
        label = str(rule["label"])
        manifest_checks.append(
            {
                "manifest": changed_file,
                "lockfiles": lockfiles,
                "changed_lockfiles": changed_lockfiles,
                "existing_lockfiles": existing_lockfiles,
                "label": label,
            }
        )

        if changed_lockfiles:
            verified.append(f"{changed_file} changed alongside {', '.join(changed_lockfiles)}")
            continue

        if existing_lockfiles:
            suspicious.append(f"{changed_file} changed without updating {', '.join(existing_lockfiles)}")
            action_items.append(f"verify dependency lockfiles for {changed_file}")
            continue

        unverified.append(f"{changed_file} changed but no known lockfile was found for {label.lower()}")
        action_items.append(f"add or verify lockfiles for {changed_file}")

    evidence = {
        "source": source,
        "notes": notes,
        "changed_files": sorted(changed_file_set),
        "manifest_checks": manifest_checks,
    }

    if not manifest_checks:
        return {
            "detector": "lockfile_drift_check",
            "status": "passed",
            "evidence": evidence,
            "verified": ["no dependency manifest changes detected"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }

    status = "passed"
    if suspicious:
        status = "failed"
    elif unverified:
        status = "partial"

    verified.extend(notes)
    return {
        "detector": "lockfile_drift_check",
        "status": status,
        "evidence": evidence,
        "verified": verified,
        "unverified": unverified,
        "suspicious": suspicious,
        "action_items": action_items,
    }
