from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import IO, Mapping


def _coerce_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _read_tail(handle: IO[str] | object, limit: int) -> str:
    if limit <= 0:
        return ""
    if not hasattr(handle, "seek") or not hasattr(handle, "read"):
        return ""
    handle.seek(0)
    data = handle.read()
    if not isinstance(data, str):
        return ""
    return data[-limit:]


def run_command(
    command: list[str],
    cwd: Path | None = None,
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,
    max_output_chars: int | None = None,
) -> tuple[int, str, str]:
    if not command:
        raise ValueError("command must not be empty")

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    if max_output_chars is None:
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

    try:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_file, tempfile.TemporaryFile(
            mode="w+",
            encoding="utf-8",
        ) as stderr_file:
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(cwd) if cwd is not None else None,
                    env=merged_env,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                stdout = _read_tail(stdout_file, max_output_chars)
                stderr = _read_tail(stderr_file, max_output_chars)
                timeout_message = f"command timed out after {timeout} seconds: {' '.join(command)}"
                stderr = f"{stderr}\n{timeout_message}".strip()
                return 124, stdout, stderr

            stdout = _read_tail(stdout_file, max_output_chars)
            stderr = _read_tail(stderr_file, max_output_chars)
            return completed.returncode, stdout, stderr
    except FileNotFoundError:
        return 127, "", f"command not found: {command[0]}"
