from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

from trust_me.utils.paths import iter_files
from trust_me.utils.subprocess import run_command
from trust_me.utils.tool_env import go_tool_env

IGNORED_PARTS = {"__pycache__", ".git", ".venv", "node_modules", "target"}
TS_EXTENSIONS = {".ts", ".tsx", ".mts", ".cts"}
GO_EXTENSIONS = {".go"}
RUST_EXTENSIONS = {".rs"}


def _python_files(root: Path) -> list[Path]:
    return sorted(iter_files(root, ignored_parts=IGNORED_PARTS, suffixes={".py"}))


def _python_targets(root: Path, python_files: list[Path]) -> list[str]:
    targets = {str((root / path.relative_to(root).parts[0])) for path in python_files}
    return sorted(targets)


def _changed_file_set(changed_files: list[str] | None) -> set[str]:
    return {Path(path).as_posix() for path in changed_files or []}


def _filter_changed_files(root: Path, files: list[Path], changed_files: list[str] | None) -> list[Path]:
    changed_set = _changed_file_set(changed_files)
    return [path for path in files if path.relative_to(root).as_posix() in changed_set]


def _typescript_files(root: Path) -> list[Path]:
    return sorted(iter_files(root, ignored_parts=IGNORED_PARTS, suffixes=TS_EXTENSIONS))


def _go_files(root: Path) -> list[Path]:
    return sorted(iter_files(root, ignored_parts=IGNORED_PARTS, suffixes=GO_EXTENSIONS))


def _rust_files(root: Path) -> list[Path]:
    return sorted(iter_files(root, ignored_parts=IGNORED_PARTS, suffixes=RUST_EXTENSIONS))


def _local_or_global_tool(root: Path, tool: str) -> str | None:
    local_candidate = root / "node_modules" / ".bin" / tool
    if local_candidate.exists():
        return str(local_candidate)
    return shutil.which(tool)


def _build_python_command(root: Path, python_files: list[Path], *, exact_targets: bool = False) -> tuple[str, list[str]] | None:
    targets = sorted(str(path) for path in python_files) if exact_targets else _python_targets(root, python_files)
    if importlib.util.find_spec("mypy") is not None:
        return "mypy", [sys.executable, "-m", "mypy", *targets]
    if shutil.which("mypy") is not None:
        return "mypy", ["mypy", *targets]
    if shutil.which("pyright") is not None:
        return "pyright", ["pyright", *targets]
    return None


def _build_typescript_command(root: Path, typescript_files: list[Path] | None = None) -> tuple[str, list[str]] | None:
    tsconfig = root / "tsconfig.json"
    if not tsconfig.exists():
        return None

    tsc = _local_or_global_tool(root, "tsc")
    if tsc is None:
        return None
    targets = [str(path) for path in typescript_files] if typescript_files else []
    return "tsc", [tsc, "--noEmit", "--pretty", "false", *targets]


def _build_go_command(root: Path, go_files: list[Path]) -> tuple[str, list[str]] | None:
    if not go_files or not (root / "go.mod").exists():
        return None
    go = shutil.which("go")
    if go is None:
        return None
    return "go test", [go, "test", "./...", "-run", "^$"]


def _build_rust_command(root: Path, rust_files: list[Path]) -> tuple[str, list[str]] | None:
    if not rust_files or not (root / "Cargo.toml").exists():
        return None
    cargo = shutil.which("cargo")
    if cargo is None:
        return None
    return "cargo check", [cargo, "check", "--quiet", "--tests"]


def _command_env(tool_name: str) -> dict[str, str] | None:
    if tool_name == "go test":
        return go_tool_env()
    return None


def _first_signal(output: str) -> str | None:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _tail(output: str, limit: int = 5) -> list[str]:
    return [line for line in output.splitlines() if line.strip()][-limit:]


def _overall_status(statuses: list[str]) -> str:
    if not statuses:
        return "skipped"
    if any(status == "failed" for status in statuses):
        return "failed"
    if any(status == "error" for status in statuses):
        return "partial" if any(status == "passed" for status in statuses) else "error"
    if all(status == "not_configured" for status in statuses):
        return "not_configured"
    if any(status == "not_configured" for status in statuses):
        return "partial"
    if all(status == "passed" for status in statuses):
        return "passed"
    return "partial"


def _run_check(
    *,
    root: Path,
    language_label: str,
    file_count: int,
    configured: tuple[str, list[str]] | None,
    not_configured_reason: str,
    install_hint: str,
) -> dict:
    if configured is None:
        return {
            "status": "not_configured",
            "verified": [],
            "unverified": [not_configured_reason],
            "suspicious": [],
            "action_items": [install_hint],
            "evidence": {"language": language_label.lower(), "file_count": file_count, "reason": "tool_not_installed"},
        }

    tool_name, command = configured
    env = _command_env(tool_name)
    code, stdout, stderr = run_command(command, cwd=root, timeout=180.0, env=env)
    evidence = {
        "language": language_label.lower(),
        "tool": tool_name,
        "command": command,
        "exit_code": code,
        "env_keys": sorted((env or {}).keys()),
        "file_count": file_count,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }

    if code == 0:
        return {
            "status": "passed",
            "verified": [f"{tool_name} passed on {file_count} {language_label} files"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
            "evidence": evidence,
        }

    if code in (124, 127):
        detail = _first_signal(stderr) or f"{tool_name} execution failed"
        return {
            "status": "error",
            "verified": [],
            "unverified": [f"{tool_name} could not complete for {language_label}: {detail}"],
            "suspicious": [],
            "action_items": [f"verify the {tool_name} type-check command is installed and runnable in this environment"],
            "evidence": evidence,
        }

    detail = _first_signal(stdout) or _first_signal(stderr) or f"{tool_name} reported type issues"
    return {
        "status": "failed",
        "verified": [],
        "unverified": [],
        "suspicious": [f"{tool_name} found type issues across {file_count} {language_label} files"],
        "action_items": [f"inspect type-check output: {detail}"],
        "evidence": evidence,
    }


def detect_type_status(
    root: Path,
    diff_range: str | None = None,
    patch_path: str | None = None,
    scope: str = "all",
    changed_files: list[str] | None = None,
) -> dict:
    python_files = _python_files(root)
    typescript_files = _typescript_files(root)
    go_files = _go_files(root)
    rust_files = _rust_files(root)
    tsconfig_exists = (root / "tsconfig.json").exists()
    selected_python_files = _filter_changed_files(root, python_files, changed_files) if scope == "changed" else python_files
    selected_typescript_files = _filter_changed_files(root, typescript_files, changed_files) if scope == "changed" else typescript_files
    selected_go_files = _filter_changed_files(root, go_files, changed_files) if scope == "changed" else go_files
    selected_rust_files = _filter_changed_files(root, rust_files, changed_files) if scope == "changed" else rust_files

    if not python_files and not typescript_files and not go_files and not rust_files and not tsconfig_exists:
        return {
            "detector": "type_check",
            "status": "skipped",
            "evidence": {"file_count": 0, "language_file_counts": {}, "checks": [], "reason": "no_supported_source_files"},
            "verified": ["no supported source files found; type check skipped"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }

    if scope == "changed" and not selected_python_files and not selected_typescript_files and not selected_go_files and not selected_rust_files:
        return {
            "detector": "type_check",
            "status": "skipped",
            "evidence": {
                "scope": scope,
                "file_count": 0,
                "language_file_counts": {
                    "python": 0,
                    "typescript": 0,
                    "go": 0,
                    "rust": 0,
                },
                "checks": [],
                "reason": "no_changed_supported_source_files",
            },
            "verified": ["no changed supported source files detected; type check skipped in changed scope"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }

    checks: list[dict] = []
    statuses: list[str] = []
    verified: list[str] = []
    unverified: list[str] = []
    suspicious: list[str] = []
    action_items: list[str] = []

    language_specs = []
    if selected_python_files:
        language_specs.append(
            (
                len(selected_python_files),
                "Python",
                _build_python_command(root, selected_python_files, exact_targets=scope == "changed"),
                "no mypy or pyright installation found; Python type status unavailable",
                "install mypy or pyright, or configure a project-specific Python type check command",
            )
        )
    if selected_typescript_files or (scope != "changed" and tsconfig_exists):
        typescript_reason = (
            "tsconfig.json is missing; TypeScript type status unavailable"
            if not tsconfig_exists
            else "tsc is not installed; TypeScript type status unavailable"
        )
        typescript_hint = (
            "add tsconfig.json so tsc --noEmit can type-check this project"
            if not tsconfig_exists
            else "install tsc or configure a project-specific TypeScript type check command"
        )
        language_specs.append((len(selected_typescript_files), "TypeScript", _build_typescript_command(root, selected_typescript_files if scope == "changed" else None), typescript_reason, typescript_hint))
    if selected_go_files:
        go_reason = "go.mod is missing; Go type status unavailable" if not (root / "go.mod").exists() else "go is not installed; Go type status unavailable"
        go_hint = (
            "add go.mod so Go type checking can be verified"
            if not (root / "go.mod").exists()
            else "install go or configure a project-specific Go type check command"
        )
        language_specs.append((len(selected_go_files), "Go", _build_go_command(root, selected_go_files), go_reason, go_hint))
    if selected_rust_files:
        rust_reason = (
            "Cargo.toml is missing; Rust type status unavailable"
            if not (root / "Cargo.toml").exists()
            else "cargo is not installed; Rust type status unavailable"
        )
        rust_hint = (
            "add Cargo.toml so Rust type checking can be verified"
            if not (root / "Cargo.toml").exists()
            else "install cargo or configure a project-specific Rust type check command"
        )
        language_specs.append((len(selected_rust_files), "Rust", _build_rust_command(root, selected_rust_files), rust_reason, rust_hint))

    for file_count, label, configured, reason, hint in language_specs:
        check = _run_check(
            root=root,
            language_label=label,
            file_count=file_count,
            configured=configured,
            not_configured_reason=reason,
            install_hint=hint,
        )
        checks.append(check["evidence"])
        statuses.append(check["status"])
        verified.extend(check["verified"])
        unverified.extend(check["unverified"])
        suspicious.extend(check["suspicious"])
        action_items.extend(check["action_items"])

    return {
        "detector": "type_check",
        "status": _overall_status(statuses),
        "evidence": {
            "scope": scope,
            "language_file_counts": {
                "python": len(selected_python_files),
                "typescript": len(selected_typescript_files),
                "go": len(selected_go_files),
                "rust": len(selected_rust_files),
            },
            "tsconfig_present": tsconfig_exists,
            "checks": checks,
        },
        "verified": verified,
        "unverified": unverified,
        "suspicious": suspicious,
        "action_items": action_items,
    }
