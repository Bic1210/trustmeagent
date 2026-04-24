from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

from trust_me.utils.subprocess import run_command
from trust_me.utils.tool_env import go_tool_env

IGNORED_PARTS = {"__pycache__", ".git", ".venv", "node_modules"}
JS_TEST_SUFFIXES = (
    ".test.js",
    ".test.jsx",
    ".test.ts",
    ".test.tsx",
    ".spec.js",
    ".spec.jsx",
    ".spec.ts",
    ".spec.tsx",
)
GO_TEST_SUFFIX = "_test.go"
RUST_EXTENSIONS = {".rs"}


def _python_test_files(root: Path) -> list[Path]:
    tests_dir = root / "tests"
    if not tests_dir.exists():
        return []

    return sorted(
        path
        for path in tests_dir.rglob("test*.py")
        if not any(part in IGNORED_PARTS for part in path.parts)
    )


def _javascript_test_files(root: Path) -> list[Path]:
    test_files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        normalized_name = path.name
        if normalized_name.endswith(JS_TEST_SUFFIXES):
            test_files.append(path)
            continue
        if "tests" in path.parts and path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
            test_files.append(path)
    return sorted(set(test_files))


def _go_test_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob(f"*{GO_TEST_SUFFIX}")
        if path.is_file() and not any(part in IGNORED_PARTS for part in path.parts)
    )


def _rust_source_files(root: Path) -> list[Path]:
    if not (root / "Cargo.toml").exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in RUST_EXTENSIONS and not any(part in IGNORED_PARTS for part in path.parts)
    )


def _local_or_global_tool(root: Path, tool: str) -> str | None:
    local_candidate = root / "node_modules" / ".bin" / tool
    if local_candidate.exists():
        return str(local_candidate)
    return shutil.which(tool)


def _read_package_json(root: Path) -> dict:
    package_json = root / "package.json"
    if not package_json.exists():
        return {}
    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _package_has_script(root: Path, script_name: str) -> bool:
    scripts = _read_package_json(root).get("scripts", {})
    return isinstance(scripts, dict) and script_name in scripts


def _available_package_manager(root: Path) -> str | None:
    if (root / "pnpm-lock.yaml").exists() and shutil.which("pnpm") is not None:
        return "pnpm"
    if (root / "yarn.lock").exists() and shutil.which("yarn") is not None:
        return "yarn"
    if shutil.which("npm") is not None:
        return "npm"
    return None


def _build_python_test_command(root: Path) -> tuple[str, list[str]] | None:
    tests_dir = root / "tests"
    if importlib.util.find_spec("pytest") is not None:
        return "pytest", [sys.executable, "-m", "pytest", "-q"]
    if shutil.which("pytest") is not None:
        return "pytest", ["pytest", "-q"]
    if tests_dir.exists():
        return "unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    return None


def _build_javascript_test_command(root: Path) -> tuple[str, list[str]] | None:
    vitest = _local_or_global_tool(root, "vitest")
    if vitest is not None:
        return "vitest", [vitest, "run"]

    jest = _local_or_global_tool(root, "jest")
    if jest is not None:
        return "jest", [jest, "--runInBand"]

    if _package_has_script(root, "test"):
        package_manager = _available_package_manager(root)
        if package_manager is not None:
            return f"{package_manager} test", [package_manager, "test"]

    return None


def _build_go_test_command(root: Path) -> tuple[str, list[str]] | None:
    if not (root / "go.mod").exists():
        return None
    go = shutil.which("go")
    if go is None:
        return None
    return "go test", [go, "test", "./..."]


def _build_rust_test_command(root: Path) -> tuple[str, list[str]] | None:
    if not (root / "Cargo.toml").exists():
        return None
    cargo = shutil.which("cargo")
    if cargo is None:
        return None
    return "cargo test", [cargo, "test", "--quiet"]


def _first_signal(output: str) -> str | None:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _tail(output: str, limit: int = 5) -> list[str]:
    return [line for line in output.splitlines() if line.strip()][-limit:]


def _extract_test_count(output: str) -> int | None:
    patterns = [
        r"\bRan (\d+) tests?\b",
        r"(\d+) passed",
        r"Tests:\s+(\d+)\s+passed",
        r"Test Files\s+(\d+)\s+passed",
        r"test result:\s+ok\.\s+(\d+)\s+passed",
    ]
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            return int(match.group(1))
    return None


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
    test_file_count: int,
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
            "evidence": {"language": language_label.lower(), "test_file_count": test_file_count, "reason": "runner_not_installed"},
        }

    runner, command = configured
    env = go_tool_env() if runner == "go test" else None
    code, stdout, stderr = run_command(command, cwd=root, timeout=180.0, env=env)
    combined_output = "\n".join(part for part in (stdout, stderr) if part)
    test_count = _extract_test_count(combined_output)
    evidence = {
        "language": language_label.lower(),
        "runner": runner,
        "command": command,
        "exit_code": code,
        "env_keys": sorted((env or {}).keys()),
        "test_file_count": test_file_count,
        "test_count": test_count,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }

    if code == 0:
        count_text = f"{test_count} tests" if test_count is not None else "tests"
        return {
            "status": "passed",
            "verified": [f"{count_text} passed via {runner} for {language_label}"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
            "evidence": evidence,
        }

    if code in (124, 127):
        detail = _first_signal(stderr) or f"{runner} execution failed"
        return {
            "status": "error",
            "verified": [],
            "unverified": [f"{runner} could not complete for {language_label}: {detail}"],
            "suspicious": [],
            "action_items": [f"verify the {runner} test command is installed and runnable in this environment"],
            "evidence": evidence,
        }

    detail = _first_signal(stdout) or _first_signal(stderr) or f"{runner} reported test failures"
    count_text = f"{test_count} tests" if test_count is not None else "tests"
    return {
        "status": "failed",
        "verified": [],
        "unverified": [],
        "suspicious": [f"{count_text} failed or did not pass via {runner} for {language_label}"],
        "action_items": [f"inspect test output: {detail}"],
        "evidence": evidence,
    }


def detect_test_status(root: Path, diff_range: str | None = None, patch_path: str | None = None) -> dict:
    python_test_files = _python_test_files(root)
    javascript_test_files = _javascript_test_files(root)
    go_test_files = _go_test_files(root)
    rust_source_files = _rust_source_files(root)

    if not python_test_files and not javascript_test_files and not go_test_files and not rust_source_files:
        return {
            "detector": "test_check",
            "status": "skipped",
            "evidence": {"test_file_count": 0, "language_test_file_counts": {}, "checks": [], "reason": "no_supported_test_files"},
            "verified": [],
            "unverified": ["no supported tests discovered; test execution skipped"],
            "suspicious": [],
            "action_items": ["add tests or configure a project-specific test command"],
        }

    checks: list[dict] = []
    statuses: list[str] = []
    verified: list[str] = []
    unverified: list[str] = []
    suspicious: list[str] = []
    action_items: list[str] = []

    if python_test_files:
        python_check = _run_check(
            root=root,
            language_label="Python",
            test_file_count=len(python_test_files),
            configured=_build_python_test_command(root),
            not_configured_reason="no supported Python test runner found; Python test status unavailable",
            install_hint="install pytest or expose a runnable Python test command",
        )
        checks.append(python_check["evidence"])
        statuses.append(python_check["status"])
        verified.extend(python_check["verified"])
        unverified.extend(python_check["unverified"])
        suspicious.extend(python_check["suspicious"])
        action_items.extend(python_check["action_items"])

    if javascript_test_files:
        javascript_check = _run_check(
            root=root,
            language_label="JavaScript/TypeScript",
            test_file_count=len(javascript_test_files),
            configured=_build_javascript_test_command(root),
            not_configured_reason="no vitest, jest, or package test script found; JavaScript/TypeScript test status unavailable",
            install_hint="install vitest or jest, or expose a runnable package test script",
        )
        checks.append(javascript_check["evidence"])
        statuses.append(javascript_check["status"])
        verified.extend(javascript_check["verified"])
        unverified.extend(javascript_check["unverified"])
        suspicious.extend(javascript_check["suspicious"])
        action_items.extend(javascript_check["action_items"])

    if go_test_files:
        go_check = _run_check(
            root=root,
            language_label="Go",
            test_file_count=len(go_test_files),
            configured=_build_go_test_command(root),
            not_configured_reason="go is not installed; Go test status unavailable",
            install_hint="install go or configure a project-specific Go test command",
        )
        checks.append(go_check["evidence"])
        statuses.append(go_check["status"])
        verified.extend(go_check["verified"])
        unverified.extend(go_check["unverified"])
        suspicious.extend(go_check["suspicious"])
        action_items.extend(go_check["action_items"])

    if rust_source_files:
        rust_check = _run_check(
            root=root,
            language_label="Rust",
            test_file_count=len(rust_source_files),
            configured=_build_rust_test_command(root),
            not_configured_reason="cargo is not installed; Rust test status unavailable",
            install_hint="install cargo or configure a project-specific Rust test command",
        )
        checks.append(rust_check["evidence"])
        statuses.append(rust_check["status"])
        verified.extend(rust_check["verified"])
        unverified.extend(rust_check["unverified"])
        suspicious.extend(rust_check["suspicious"])
        action_items.extend(rust_check["action_items"])

    return {
        "detector": "test_check",
        "status": _overall_status(statuses),
        "evidence": {
            "language_test_file_counts": {
                "python": len(python_test_files),
                "javascript_or_typescript": len(javascript_test_files),
                "go": len(go_test_files),
                "rust": len(rust_source_files),
            },
            "checks": checks,
        },
        "verified": verified,
        "unverified": unverified,
        "suspicious": suspicious,
        "action_items": action_items,
    }
