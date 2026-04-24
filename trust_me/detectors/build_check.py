from __future__ import annotations

import shutil
import sys
from pathlib import Path

from trust_me.utils.subprocess import run_command
from trust_me.utils.tool_env import go_tool_env


def _tail(output: str, limit: int = 5) -> list[str]:
    return [line for line in output.splitlines() if line.strip()][-limit:]


def _first_signal(output: str) -> str | None:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _has_python_files(root: Path) -> bool:
    return any(
        path.suffix == ".py" and "__pycache__" not in path.parts and ".git" not in path.parts and ".venv" not in path.parts
        for path in root.rglob("*.py")
    )


def _build_command(root: Path) -> tuple[str, list[str]] | None:
    if (root / "Cargo.toml").exists() and shutil.which("cargo") is not None:
        return "cargo", ["cargo", "check", "--quiet"]

    if (root / "go.mod").exists() and shutil.which("go") is not None:
        return "go", ["go", "build", "./..."]

    if (root / "tsconfig.json").exists() and shutil.which("tsc") is not None:
        return "tsc", ["tsc", "--noEmit"]

    if (root / "pyproject.toml").exists() or _has_python_files(root):
        return "compileall", [sys.executable, "-m", "compileall", str(root)]

    return None


def _command_env(tool: str) -> dict[str, str] | None:
    if tool == "go":
        return go_tool_env()
    return None


def detect_build_status(root: Path, diff_range: str | None = None, patch_path: str | None = None) -> dict:
    configured = _build_command(root)
    if configured is None:
        return {
            "detector": "build_check",
            "status": "skipped",
            "evidence": {"reason": "no_supported_build_target"},
            "verified": [],
            "unverified": ["no supported build target detected for build_check"],
            "suspicious": [],
            "action_items": ["add a supported manifest or configure a project-specific build detector"],
        }

    tool, command = configured
    code, stdout, stderr = run_command(command, cwd=root, timeout=120.0, env=_command_env(tool))
    evidence = {
        "tool": tool,
        "command": command,
        "exit_code": code,
        "env_keys": sorted((_command_env(tool) or {}).keys()),
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
