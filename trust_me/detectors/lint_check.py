from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

from trust_me.utils.paths import iter_files
from trust_me.utils.subprocess import run_command

IGNORED_PARTS = {"__pycache__", ".git", ".venv", "node_modules", "target"}
JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
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


def _javascript_files(root: Path) -> list[Path]:
    return sorted(iter_files(root, ignored_parts=IGNORED_PARTS, suffixes=JS_EXTENSIONS))


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
    if importlib.util.find_spec("ruff") is not None:
        return "ruff", [sys.executable, "-m", "ruff", "check", *targets]
    if shutil.which("ruff") is not None:
        return "ruff", ["ruff", "check", *targets]
    return None


def _build_javascript_command(root: Path, javascript_files: list[Path] | None = None) -> tuple[str, list[str]] | None:
    targets = [str(path) for path in javascript_files] if javascript_files else ["."]
    eslint = _local_or_global_tool(root, "eslint")
    if eslint is not None:
        return "eslint", [eslint, *targets]

    biome = _local_or_global_tool(root, "biome")
    if biome is not None:
        return "biome", [biome, "check", *targets]

    return None


def _build_go_command(go_files: list[Path]) -> tuple[str, list[str]] | None:
    gofmt = shutil.which("gofmt")
    if gofmt is None or not go_files:
        return None
    return "gofmt", [gofmt, "-l", *[str(path) for path in go_files]]


def _build_rust_command(root: Path, rust_files: list[Path]) -> tuple[str, list[str]] | None:
    if not rust_files or not (root / "Cargo.toml").exists():
        return None
    if shutil.which("rustfmt") is None:
        return None
    cargo = shutil.which("cargo")
    if cargo is None:
        return None
    return "cargo fmt", [cargo, "fmt", "--all", "--", "--check"]


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
    code, stdout, stderr = run_command(command, cwd=root, timeout=120.0)
    evidence = {
        "language": language_label.lower(),
        "tool": tool_name,
        "command": command,
        "exit_code": code,
        "file_count": file_count,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }

    if tool_name == "gofmt" and stdout.strip():
        detail = _first_signal(stdout) or "gofmt reported unformatted files"
        return {
            "status": "failed",
            "verified": [],
            "unverified": [],
            "suspicious": [f"gofmt found formatting issues across {file_count} Go files"],
            "action_items": [f"inspect lint output: {detail}"],
            "evidence": evidence,
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
            "action_items": [f"verify the {tool_name} lint command is installed and runnable in this environment"],
            "evidence": evidence,
        }

    detail = _first_signal(stdout) or _first_signal(stderr) or f"{tool_name} reported lint issues"
    return {
        "status": "failed",
        "verified": [],
        "unverified": [],
        "suspicious": [f"{tool_name} found lint issues across {file_count} {language_label} files"],
        "action_items": [f"inspect lint output: {detail}"],
        "evidence": evidence,
    }


def detect_lint_status(
    root: Path,
    diff_range: str | None = None,
    patch_path: str | None = None,
    scope: str = "all",
    changed_files: list[str] | None = None,
) -> dict:
    python_files = _python_files(root)
    javascript_files = _javascript_files(root)
    go_files = _go_files(root)
    rust_files = _rust_files(root)
    selected_python_files = _filter_changed_files(root, python_files, changed_files) if scope == "changed" else python_files
    selected_javascript_files = _filter_changed_files(root, javascript_files, changed_files) if scope == "changed" else javascript_files
    selected_go_files = _filter_changed_files(root, go_files, changed_files) if scope == "changed" else go_files
    selected_rust_files = _filter_changed_files(root, rust_files, changed_files) if scope == "changed" else rust_files

    if not python_files and not javascript_files and not go_files and not rust_files:
        return {
            "detector": "lint_check",
            "status": "skipped",
            "evidence": {"file_count": 0, "language_file_counts": {}, "checks": [], "reason": "no_supported_source_files"},
            "verified": ["no supported source files found; lint check skipped"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }

    if scope == "changed" and not selected_python_files and not selected_javascript_files and not selected_go_files and not selected_rust_files:
        return {
            "detector": "lint_check",
            "status": "skipped",
            "evidence": {
                "scope": scope,
                "file_count": 0,
                "language_file_counts": {
                    "python": 0,
                    "javascript_or_typescript": 0,
                    "go": 0,
                    "rust": 0,
                },
                "checks": [],
                "reason": "no_changed_supported_source_files",
            },
            "verified": ["no changed supported source files detected; lint check skipped in changed scope"],
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

    language_specs = [
        (
            selected_python_files,
            "Python",
            _build_python_command(root, selected_python_files, exact_targets=scope == "changed"),
            "ruff is not installed; Python lint status unavailable",
            "install ruff or configure an alternative Python lint command",
        ),
        (
            selected_javascript_files,
            "JavaScript/TypeScript",
            _build_javascript_command(root, selected_javascript_files if scope == "changed" else None),
            "no eslint or biome installation found; JavaScript/TypeScript lint status unavailable",
            "install eslint or biome, or configure a project-specific JavaScript/TypeScript lint command",
        ),
        (
            selected_go_files,
            "Go",
            _build_go_command(selected_go_files),
            "gofmt is not installed; Go lint status unavailable",
            "install gofmt or configure a project-specific Go lint command",
        ),
        (
            selected_rust_files,
            "Rust",
            _build_rust_command(root, selected_rust_files),
            "rustfmt is not installed; Rust lint status unavailable",
            "install rustfmt or configure a project-specific Rust lint command",
        ),
    ]

    for files, label, configured, not_configured_reason, install_hint in language_specs:
        if not files:
            continue
        check = _run_check(
            root=root,
            language_label=label,
            file_count=len(files),
            configured=configured,
            not_configured_reason=not_configured_reason,
            install_hint=install_hint,
        )
        checks.append(check["evidence"])
        statuses.append(check["status"])
        verified.extend(check["verified"])
        unverified.extend(check["unverified"])
        suspicious.extend(check["suspicious"])
        action_items.extend(check["action_items"])

    return {
        "detector": "lint_check",
        "status": _overall_status(statuses),
        "evidence": {
            "scope": scope,
            "language_file_counts": {
                "python": len(selected_python_files),
                "javascript_or_typescript": len(selected_javascript_files),
                "go": len(selected_go_files),
                "rust": len(selected_rust_files),
            },
            "checks": checks,
        },
        "verified": verified,
        "unverified": unverified,
        "suspicious": suspicious,
        "action_items": action_items,
    }
