from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping


def _coerce_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def run_command(
    command: list[str],
    cwd: Path | None = None,
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[int, str, str]:
    if not command:
        raise ValueError("command must not be empty")

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            env=merged_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, "", f"command not found: {command[0]}"
    except subprocess.TimeoutExpired as exc:
        stdout = _coerce_output(exc.stdout)
        stderr = _coerce_output(exc.stderr)
        timeout_message = f"command timed out after {timeout} seconds: {' '.join(command)}"
        stderr = f"{stderr}\n{timeout_message}".strip()
        return 124, stdout, stderr

    return completed.returncode, completed.stdout, completed.stderr
