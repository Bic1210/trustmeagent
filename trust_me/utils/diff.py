from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from trust_me.utils.git import read_diff_for_range, read_working_tree_diff, read_working_tree_status, repo_root


def load_patch_text(root: Path, patch_path: str | None, diff_range: str | None) -> tuple[str | None, str | None, str, list[str]]:
    notes: list[str] = []
    if patch_path is not None:
        patch_file = Path(patch_path)
        if not patch_file.is_absolute():
            patch_file = root / patch_file
        try:
            return patch_file.read_text(encoding="utf-8"), "patch_file", "", notes
        except OSError as exc:
            return None, "patch_file", f"could not read patch file: {exc}", notes

    if diff_range is not None:
        code, stdout, stderr = read_diff_for_range(root, diff_range)
        if code != 0:
            return None, "git_diff_range", stderr or "git diff failed", notes
        return stdout, "git_diff_range", "", notes

    repo = repo_root(root)
    if repo is None:
        return None, "working_tree", "not a git repository", notes

    status_code, status_stdout, status_stderr = read_working_tree_status(root)
    if status_code != 0:
        return None, "working_tree", status_stderr or "git status failed", notes

    untracked = [line[3:] for line in status_stdout.splitlines() if line.startswith("?? ")]
    if untracked:
        notes.append(f"{len(untracked)} untracked files are present and excluded from hunk counts")

    diff_code, diff_stdout, diff_stderr = read_working_tree_diff(root)
    if diff_code != 0:
        return None, "working_tree", diff_stderr or "git diff failed", notes
    return diff_stdout, "working_tree", "", notes


def parse_diff_scope(diff_text: str) -> dict:
    files: set[str] = set()
    hunk_count = 0
    added_lines = 0
    removed_lines = 0
    binary_files = 0
    file_types: Counter[str] = Counter()

    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path == "/dev/null":
                continue
            if path.startswith("b/"):
                path = path[2:]
            files.add(path)
            suffix = Path(path).suffix or "[no_extension]"
            file_types[suffix] += 1
            continue

        if line.startswith("Binary files "):
            binary_files += 1
            continue

        if line.startswith("@@ "):
            hunk_count += 1
            continue

        if line.startswith("+") and not line.startswith("+++"):
            added_lines += 1
            continue

        if line.startswith("-") and not line.startswith("---"):
            removed_lines += 1

    return {
        "changed_files": sorted(files),
        "file_count": len(files),
        "hunk_count": hunk_count,
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "binary_files": binary_files,
        "file_types": dict(file_types),
    }


def load_changed_files(
    root: Path,
    patch_path: str | None,
    diff_range: str | None,
) -> tuple[list[str] | None, str | None, str, list[str], dict[str, Any] | None]:
    diff_text, source, error, notes = load_patch_text(root, patch_path, diff_range)
    if error:
        return None, source, error, notes, None
    if diff_text is None:
        return None, source, "missing_diff_text", notes, None

    parsed = parse_diff_scope(diff_text)
    return list(parsed["changed_files"]), source, "", notes, parsed
