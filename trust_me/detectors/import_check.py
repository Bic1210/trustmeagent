from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

from trust_me.utils.subprocess import run_command
from trust_me.utils.tool_env import go_tool_env

IGNORED_PARTS = {"__pycache__", ".git", ".venv", "node_modules"}
PYTHON_EXTENSIONS = {".py"}
JAVASCRIPT_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs"}
TYPESCRIPT_EXTENSIONS = {".ts", ".tsx", ".mts", ".cts"}
GO_EXTENSIONS = {".go"}
RUST_EXTENSIONS = {".rs"}
UNSUPPORTED_LANGUAGE_EXTENSIONS = {
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
}
JS_RESOLUTION_EXTENSIONS = [".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".json"]
NODE_BUILTIN_MODULES = {
    "assert",
    "buffer",
    "child_process",
    "crypto",
    "events",
    "fs",
    "http",
    "https",
    "net",
    "os",
    "path",
    "stream",
    "timers",
    "tty",
    "url",
    "util",
    "zlib",
}
IMPORT_PATTERNS = [
    re.compile(r"""(?m)^\s*import\s+(?:.+?\s+from\s+)?["']([^"']+)["']"""),
    re.compile(r"""(?m)^\s*export\s+.+?\s+from\s+["']([^"']+)["']"""),
    re.compile(r"""require\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""import\(\s*["']([^"']+)["']\s*\)"""),
]


def _all_source_files(root: Path) -> list[Path]:
    extensions = (
        PYTHON_EXTENSIONS
        | JAVASCRIPT_EXTENSIONS
        | TYPESCRIPT_EXTENSIONS
        | GO_EXTENSIONS
        | RUST_EXTENSIONS
        | set(UNSUPPORTED_LANGUAGE_EXTENSIONS)
    )
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in extensions and not any(part in IGNORED_PARTS for part in path.parts)
    )


def _python_files(files: list[Path]) -> list[Path]:
    return [path for path in files if path.suffix in PYTHON_EXTENSIONS]


def _javascript_files(files: list[Path]) -> list[Path]:
    return [path for path in files if path.suffix in JAVASCRIPT_EXTENSIONS | TYPESCRIPT_EXTENSIONS]


def _go_files(files: list[Path]) -> list[Path]:
    return [path for path in files if path.suffix in GO_EXTENSIONS]


def _rust_files(files: list[Path]) -> list[Path]:
    return [path for path in files if path.suffix in RUST_EXTENSIONS]


def _unsupported_language_counts(files: list[Path]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in files:
        language = UNSUPPORTED_LANGUAGE_EXTENSIONS.get(path.suffix)
        if language is None:
            continue
        counts[language] = counts.get(language, 0) + 1
    return counts


def _module_name_for_path(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    parts = list(relative.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join(parts)


def _local_python_modules(root: Path, python_files: list[Path]) -> set[str]:
    modules: set[str] = set()
    for path in python_files:
        module_name = _module_name_for_path(root, path)
        if not module_name:
            continue
        parts = module_name.split(".")
        for index in range(1, len(parts) + 1):
            modules.add(".".join(parts[:index]))
    return modules


def _can_find_spec(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _python_module_known(module_name: str, local_modules: set[str]) -> bool:
    if not module_name:
        return False
    if module_name in local_modules:
        return True

    top_level = module_name.split(".")[0]
    if top_level in getattr(sys, "stdlib_module_names", set()):
        return True

    return _can_find_spec(module_name) or _can_find_spec(top_level)


def _resolve_relative_base(module_name: str, level: int, imported_module: str | None) -> str | None:
    package_parts = module_name.split(".")[:-1]
    if level > len(package_parts):
        return None

    anchor = package_parts[: len(package_parts) - level + 1]
    if imported_module:
        anchor.append(imported_module)
    return ".".join(anchor)


def _format_missing(relative_path: Path, statement: str) -> str:
    return f"{relative_path}: {statement}"


def _scan_python_imports(root: Path, path: Path, local_modules: set[str]) -> tuple[list[str], str | None]:
    relative_path = path.relative_to(root)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [], f"{relative_path}: could not parse file for import scan ({exc})"

    module_name = _module_name_for_path(root, path)
    missing: list[str] = []
    local_prefixes = {name for name in local_modules if "." in name or name}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported = alias.name
                if not _python_module_known(imported, local_modules):
                    missing.append(_format_missing(relative_path, f"import {imported}"))

        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = _resolve_relative_base(module_name, node.level, node.module)
                if base is None:
                    missing.append(_format_missing(relative_path, "invalid relative import"))
                    continue

                for alias in node.names:
                    if alias.name == "*":
                        if not _python_module_known(base, local_modules):
                            missing.append(_format_missing(relative_path, f"from {'.' * node.level}{node.module or ''} import *"))
                        continue

                    candidate = f"{base}.{alias.name}" if base else alias.name
                    if candidate in local_modules or base in local_modules:
                        continue
                    missing.append(_format_missing(relative_path, f"from {'.' * node.level}{node.module or ''} import {alias.name}"))
                continue

            base = node.module or ""
            if not base:
                continue

            base_is_local = base in local_modules or any(name.startswith(f"{base}.") for name in local_prefixes)
            if base_is_local:
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = f"{base}.{alias.name}"
                    if candidate in local_modules or base in local_modules:
                        continue
                    missing.append(_format_missing(relative_path, f"from {base} import {alias.name}"))
                continue

            if not _python_module_known(base, local_modules):
                missing.append(_format_missing(relative_path, f"from {base} import ..."))

    return missing, None


def _declared_js_packages(root: Path) -> set[str]:
    packages: set[str] = set()
    for package_json in root.rglob("package.json"):
        if any(part in IGNORED_PARTS for part in package_json.parts):
            continue
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            entries = payload.get(field, {})
            if isinstance(entries, dict):
                packages.update(entries.keys())
    return packages


def _extract_js_imports(source: str) -> list[str]:
    imports: list[str] = []
    for pattern in IMPORT_PATTERNS:
        imports.extend(match.group(1) for match in pattern.finditer(source))
    return imports


def _js_package_name(specifier: str) -> str:
    if specifier.startswith("@"):
        parts = specifier.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else specifier
    return specifier.split("/")[0]


def _resolve_js_relative_import(path: Path, specifier: str) -> bool:
    base = (path.parent / specifier).resolve()
    candidates = [base]
    if base.suffix:
        candidates.append(base.with_suffix(base.suffix))
    else:
        candidates.extend(base.with_suffix(ext) for ext in JS_RESOLUTION_EXTENSIONS)
    candidates.extend((base / "index").with_suffix(ext) for ext in JS_RESOLUTION_EXTENSIONS)
    return any(candidate.exists() for candidate in candidates)


def _scan_javascript_imports(root: Path, path: Path, declared_packages: set[str]) -> tuple[list[str], str | None]:
    relative_path = path.relative_to(root)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], f"{relative_path}: could not read file for import scan ({exc})"

    missing: list[str] = []
    for specifier in _extract_js_imports(source):
        if "://" in specifier:
            continue
        if specifier.startswith("node:"):
            continue
        if specifier.startswith(("./", "../")):
            if not _resolve_js_relative_import(path, specifier):
                missing.append(_format_missing(relative_path, f"import {specifier}"))
            continue

        if specifier.startswith("/"):
            missing.append(_format_missing(relative_path, f"import {specifier}"))
            continue

        package_name = _js_package_name(specifier)
        if package_name in NODE_BUILTIN_MODULES or package_name in declared_packages:
            continue
        missing.append(_format_missing(relative_path, f"import {specifier}"))

    return missing, None


def _first_signal(output: str) -> str | None:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _tail(output: str, limit: int = 5) -> list[str]:
    return [line for line in output.splitlines() if line.strip()][-limit:]


def _go_import_check(root: Path, go_files: list[Path]) -> dict:
    if not go_files:
        return {"status": "skipped", "verified": [], "unverified": [], "suspicious": [], "action_items": [], "evidence": {}}
    if not (root / "go.mod").exists():
        return {
            "status": "not_configured",
            "verified": [],
            "unverified": ["go.mod is missing; Go import status unavailable"],
            "suspicious": [],
            "action_items": ["add go.mod so Go import resolution can be verified"],
            "evidence": {"tool": "go", "reason": "missing_go_mod", "file_count": len(go_files)},
        }

    code, stdout, stderr = run_command(["go", "list", "./..."], cwd=root, timeout=120.0, env=go_tool_env())
    evidence = {
        "tool": "go",
        "command": ["go", "list", "./..."],
        "exit_code": code,
        "file_count": len(go_files),
        "env_keys": ["GOCACHE", "GOPATH"],
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }
    if code == 0:
        return {
            "status": "passed",
            "verified": [f"no unresolved Go imports detected across {len(go_files)} files"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
            "evidence": evidence,
        }

    detail = _first_signal(stderr) or _first_signal(stdout) or "go import resolution failed"
    return {
        "status": "failed",
        "verified": [],
        "unverified": [],
        "suspicious": [f"found unresolved Go imports across {len(go_files)} files"],
        "action_items": [f"inspect Go import resolution output: {detail}"],
        "evidence": evidence,
    }


def _rust_import_check(root: Path, rust_files: list[Path]) -> dict:
    if not rust_files:
        return {"status": "skipped", "verified": [], "unverified": [], "suspicious": [], "action_items": [], "evidence": {}}
    if not (root / "Cargo.toml").exists():
        return {
            "status": "not_configured",
            "verified": [],
            "unverified": ["Cargo.toml is missing; Rust import status unavailable"],
            "suspicious": [],
            "action_items": ["add Cargo.toml so Rust import resolution can be verified"],
            "evidence": {"tool": "cargo", "reason": "missing_cargo_toml", "file_count": len(rust_files)},
        }

    code, stdout, stderr = run_command(["cargo", "check", "--quiet"], cwd=root, timeout=180.0)
    evidence = {
        "tool": "cargo",
        "command": ["cargo", "check", "--quiet"],
        "exit_code": code,
        "file_count": len(rust_files),
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }
    if code == 0:
        return {
            "status": "passed",
            "verified": [f"no unresolved Rust imports detected across {len(rust_files)} files"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
            "evidence": evidence,
        }

    detail = _first_signal(stderr) or _first_signal(stdout) or "cargo import resolution failed"
    return {
        "status": "failed",
        "verified": [],
        "unverified": [],
        "suspicious": [f"found unresolved Rust imports across {len(rust_files)} files"],
        "action_items": [f"inspect Rust import resolution output: {detail}"],
        "evidence": evidence,
    }


def _build_evidence(
    python_files: list[Path],
    javascript_files: list[Path],
    go_files: list[Path],
    rust_files: list[Path],
    python_missing: list[str],
    js_missing: list[str],
    parse_errors: list[str],
    unsupported_languages: dict[str, int],
    language_checks: list[dict],
) -> dict:
    return {
        "language_file_counts": {
            "python": len(python_files),
            "javascript_or_typescript": len(javascript_files),
            "go": len(go_files),
            "rust": len(rust_files),
            **unsupported_languages,
        },
        "missing_count": len(python_missing) + len(js_missing),
        "parse_error_count": len(parse_errors),
        "missing_imports": {
            "python": python_missing[:10],
            "javascript_or_typescript": js_missing[:10],
        },
        "parse_errors": parse_errors[:10],
        "unsupported_languages": unsupported_languages,
        "checks": language_checks,
    }


def detect_missing_import_risk(root: Path, diff_range: str | None = None, patch_path: str | None = None) -> dict:
    source_files = _all_source_files(root)
    if not source_files:
        return {
            "detector": "import_check",
            "status": "skipped",
            "evidence": {"reason": "no_supported_source_files", "language_file_counts": {}},
            "verified": ["no supported source files found; import scan skipped"],
            "unverified": [],
            "suspicious": [],
            "action_items": [],
        }

    python_files = _python_files(source_files)
    javascript_files = _javascript_files(source_files)
    go_files = _go_files(source_files)
    rust_files = _rust_files(source_files)
    unsupported_languages = _unsupported_language_counts(source_files)

    python_missing: list[str] = []
    js_missing: list[str] = []
    parse_errors: list[str] = []

    if python_files:
        local_modules = _local_python_modules(root, python_files)
        for path in python_files:
            file_missing, parse_error = _scan_python_imports(root, path, local_modules)
            python_missing.extend(file_missing)
            if parse_error is not None:
                parse_errors.append(parse_error)

    if javascript_files:
        declared_packages = _declared_js_packages(root)
        for path in javascript_files:
            file_missing, parse_error = _scan_javascript_imports(root, path, declared_packages)
            js_missing.extend(file_missing)
            if parse_error is not None:
                parse_errors.append(parse_error)

    go_check = _go_import_check(root, go_files)
    rust_check = _rust_import_check(root, rust_files)
    language_checks = [check["evidence"] for check in (go_check, rust_check) if check["evidence"]]

    evidence = _build_evidence(
        python_files=python_files,
        javascript_files=javascript_files,
        go_files=go_files,
        rust_files=rust_files,
        python_missing=python_missing,
        js_missing=js_missing,
        parse_errors=parse_errors,
        unsupported_languages=unsupported_languages,
        language_checks=language_checks,
    )

    verified: list[str] = []
    if python_files and not python_missing:
        verified.append(f"no unresolved Python imports detected across {len(python_files)} files")
    if javascript_files and not js_missing:
        verified.append(f"no unresolved JavaScript/TypeScript imports detected across {len(javascript_files)} files")
    verified.extend(go_check["verified"])
    verified.extend(rust_check["verified"])

    unverified = [
        f"import scan for {language} files is not implemented yet ({count} files)"
        for language, count in sorted(unsupported_languages.items())
    ]
    if parse_errors and not (python_missing or js_missing):
        unverified.append(f"import scan incomplete; {len(parse_errors)} files could not be parsed")
    unverified.extend(go_check["unverified"])
    unverified.extend(rust_check["unverified"])

    suspicious: list[str] = []
    action_items: list[str] = []
    if python_missing:
        suspicious.append(f"found {len(python_missing)} unresolved import references across {len(python_files)} Python files")
        action_items.append(f"inspect Python import scan findings: {python_missing[0]}")
    if js_missing:
        suspicious.append(
            f"found {len(js_missing)} unresolved import references across {len(javascript_files)} JavaScript/TypeScript files"
        )
        action_items.append(f"inspect JavaScript/TypeScript import scan findings: {js_missing[0]}")
    if parse_errors:
        action_items.append(f"fix parse/read errors in import scan: {parse_errors[0]}")
    suspicious.extend(go_check["suspicious"])
    suspicious.extend(rust_check["suspicious"])
    action_items.extend(go_check["action_items"])
    action_items.extend(rust_check["action_items"])

    status = "passed"
    if suspicious:
        status = "failed"
    elif unverified and verified:
        status = "partial"
    elif unverified and not verified:
        status = "not_configured" if all("unavailable" in item or "not implemented yet" in item for item in unverified) else "partial"

    return {
        "detector": "import_check",
        "status": status,
        "evidence": evidence,
        "verified": verified,
        "unverified": unverified,
        "suspicious": suspicious,
        "action_items": action_items,
    }
