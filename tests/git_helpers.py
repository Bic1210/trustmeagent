from __future__ import annotations

from pathlib import Path

from trust_me.utils.subprocess import run_command


def git_ok(root: Path, *args: str) -> str:
    code, stdout, stderr = run_command(["git", *args], cwd=root, timeout=30.0)
    if code != 0:
        detail = stderr.strip() or stdout.strip() or f"git {' '.join(args)} failed"
        raise AssertionError(detail)
    return stdout


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def init_repo(root: Path, files: dict[str, str]) -> None:
    git_ok(root, "init")
    git_ok(root, "config", "user.name", "Test User")
    git_ok(root, "config", "user.email", "test@example.com")
    write_files(root, files)
    git_ok(root, "add", ".")
    git_ok(root, "commit", "-m", "initial")


def commit_files(root: Path, files: dict[str, str], message: str) -> None:
    write_files(root, files)
    git_ok(root, "add", ".")
    git_ok(root, "commit", "-m", message)
