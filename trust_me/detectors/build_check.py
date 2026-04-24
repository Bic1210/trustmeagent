from __future__ import annotations

import shutil
import sys
from pathlib import Path

from trust_me.utils.paths import iter_files
from trust_me.utils.subprocess import run_command
from trust_me.utils.tool_env import go_tool_env

IGNORED_PARTS = {"__pycache__", ".git", ".venv", "node_modules", ".mypy_cache", ".ruff_cache"}


def _tail(output: str, limit: int = 5) -> list[str]:
    return [line for line in output.splitlines() if line.strip()][-limit:]


def _first_signal(output: str) -> str | None:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _has_python_files(root: Path) -> bool:
    return any(iter_files(root, ignored_parts=IGNORED_PARTS, suffixes={".py"}))


def _directory_has_python_files(path: Path) -> bool:
    return any(iter_files(path, ignored_parts=IGNORED_PARTS, suffixes={".py"}))


def _python_build_targets(root: Path) -> list[str]:
    targets: list[str] = []
    for path in sorted(root.iterdir()):
        if path.name in IGNORED_PARTS:
            continue
        if path.is_file() and path.suffix == ".py":
            targets.append(str(path))
            continue
        if path.is_dir() and _directory_has_python_files(path):
            targets.append(str(path))
    return targets


def _changed_file_set(changed_files: list[str] | None) -> set[str]:
    return {Path(path).as_posix() for path in changed_files or []}


def _filter_changed_files(root: Path, files: list[Path], changed_files: list[str] | None) -> list[Path]:
    changed_set = _changed_file_set(changed_files)
    return [path for path in files if path.relative_to(root).as_posix() in changed_set]


def _build_command(
    root: Path,
    *,
    python_targets: list[str] | None = None,
    typescript_targets: list[str] | None = None,
    allow_go: bool = True,
    allow_rust: bool = True,
) -> tuple[str, list[str]] | None:
    if allow_rust and (root / "Cargo.toml").exists() and shutil.which("cargo") is not None:
        return "cargo", ["cargo", "check", "--quiet"]

    if allow_go and (root / "go.mod").exists() and shutil.which("go") is not None:
        return "go", ["go", "build", "./..."]

    if (root / "tsconfig.json").exists() and shutil.which("tsc") is not None:
        return "tsc", ["tsc", "--noEmit", *(typescript_targets or [])]

    if (root / "pyproject.toml").exists() or _has_python_files(root):
        targets = python_targets or _python_build_targets(root)
        if not targets:
            targets = [str(root)]
        return "compileall", [sys.executable, "-m", "compileall", *targets]

    return None


def _command_env(tool: str) -> dict[str, str] | None:
    if tool == "go":
        return go_tool_env()
    return None


def detect_build_status(
    root: Path,
    diff_range: str | None = None,
    patch_path: str | None = None,
    scope: str = "all",
    changed_files: list[str] | None = None,
) -> dict:
    python_files = sorted(iter_files(root, ignored_parts=IGNORED_PARTS, suffixes={".py"}))
    typescript_files = sorted(iter_files(root, ignored_parts=IGNORED_PARTS, suffixes={".ts", ".tsx", ".mts", ".cts"}))
    go_files = sorted(iter_files(root, ignored_parts=IGNORED_PARTS, suffixes={".go"}))
    rust_files = sorted(iter_files(root, ignored_parts=IGNORED_PARTS, suffixes={".rs"}))

    selected_python_files = _filter_changed_files(root, python_files, changed_files) if scope == "changed" else python_files
    selected_typescript_files = _filter_changed_files(root, typescript_files, changed_files) if scope == "changed" else typescript_files
    selected_go_files = _filter_changed_files(root, go_files, changed_files) if scope == "changed" else go_files
    selected_rust_files = _filter_changed_files(root, rust_files, changed_files) if scope == "changed" else rust_files

    if scope == "changed" and not selected_python_files and not selected_typescript_files and not selected_go_files and not selected_rust_files:
        return {
            "detector": "build_check",
            "status": "skipped",
            "evidence": {
                "scope": scope,
                "reason": "no_changed_supported_build_target",
                "language_file_counts": {
                    "python": 0,
                    "typescript": 0,
                    "go": 0,
                    "rust": 0,
                },
            },
            "verified": ["no changed supported build targets detected; build check skipped in changed scope"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }

    configured = _build_command(
        root,
        python_targets=[str(path) for path in selected_python_files] if scope == "changed" else None,
        typescript_targets=[str(path) for path in selected_typescript_files] if scope == "changed" else None,
        allow_go=bool(selected_go_files) if scope == "changed" else True,
        allow_rust=bool(selected_rust_files) if scope == "changed" else True,
    )
    if configured is None:
        return {
            "detector": "build_check",
            "status": "skipped",
            "evidence": {"scope": scope, "reason": "no_supported_build_target"},
            "verified": [],
            "unverified": ["no supported build target detected for build_check"],
            "suspicious": [],
            "action_items": ["add a supported manifest or configure a project-specific build detector"],
        }

    tool, command = configured
    code, stdout, stderr = run_command(command, cwd=root, timeout=120.0, env=_command_env(tool))
    evidence = {
        "scope": scope,
        "tool": tool,
        "command": command,
        "exit_code": code,
        "env_keys": sorted((_command_env(tool) or {}).keys()),
        "language_file_counts": {
            "python": len(selected_python_files),
            "typescript": len(selected_typescript_files),
            "go": len(selected_go_files),
            "rust": len(selected_rust_files),
        },
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }

    if code == 0:
        return {
            "detector": "build_check",
            "status": "passed",
            "evidence": evidence,
            "verified": [f"{tool} build smoke check passed"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }

    if code in (124, 127):
        detail = _first_signal(stderr) or f"{tool} execution failed"
        return {
            "detector": "build_check",
            "status": "error",
            "evidence": evidence,
            "verified": [],
            "unverified": [f"{tool} could not complete: {detail}"],
            "suspicious": [],
            "action_items": ["verify the build tool is installed and runnable in this environment"],
        }

    detail = _first_signal(stdout) or _first_signal(stderr) or f"{tool} reported build failures"
    return {
        "detector": "build_check",
        "status": "failed",
        "evidence": evidence,
        "verified": [],
        "unverified": [],
        "suspicious": [f"{tool} build smoke check failed"],
        "action_items": [f"inspect build output: {detail}"],
    }
