from __future__ import annotations

from pathlib import Path

from trust_me.utils.subprocess import run_command


def repo_root(path: Path) -> Path | None:
    code, stdout, _stderr = run_command(["git", "rev-parse", "--show-toplevel"], cwd=path)
    if code != 0:
        return None
    root = stdout.strip()
    if not root:
        return None
    return Path(root)


def read_diff_for_range(path: Path, diff_range: str) -> tuple[int, str, str]:
    root = repo_root(path)
    if root is None:
        return 1, "", "not a git repository"
    return run_command(["git", "diff", "--no-ext-diff", "--no-color", diff_range], cwd=root, timeout=30.0)


def read_working_tree_diff(path: Path) -> tuple[int, str, str]:
    root = repo_root(path)
    if root is None:
        return 1, "", "not a git repository"

    unstaged_code, unstaged_stdout, unstaged_stderr = run_command(
        ["git", "diff", "--no-ext-diff", "--no-color"],
        cwd=root,
        timeout=30.0,
    )
    if unstaged_code != 0:
        return unstaged_code, unstaged_stdout, unstaged_stderr

    staged_code, staged_stdout, staged_stderr = run_command(
        ["git", "diff", "--no-ext-diff", "--no-color", "--cached"],
        cwd=root,
        timeout=30.0,
    )
    if staged_code != 0:
        return staged_code, staged_stdout, staged_stderr

    parts = [part for part in (unstaged_stdout.strip(), staged_stdout.strip()) if part]
    combined = "\n".join(parts)
    return 0, combined, ""


def read_working_tree_status(path: Path) -> tuple[int, str, str]:
    root = repo_root(path)
    if root is None:
        return 1, "", "not a git repository"
    return run_command(["git", "status", "--short"], cwd=root, timeout=15.0)
