from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Iterator


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def runs_root(root: Path) -> Path:
    return ensure_dir(root / "runs")


def make_run_dir(root: Path, timestamp: datetime | None = None) -> Path:
    moment = timestamp or datetime.now()
    base = moment.strftime("run_%Y_%m_%d_%H%M%S")
    parent = runs_root(root)
    directory = parent / base
    suffix = 1
    while directory.exists():
        directory = parent / f"{base}_{suffix:02d}"
        suffix += 1
    return ensure_dir(directory)


def iter_files(
    root: Path,
    *,
    ignored_parts: set[str],
    suffixes: set[str] | None = None,
    exact_names: set[str] | None = None,
) -> Iterator[Path]:
    if not root.exists():
        return

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in ignored_parts)
        base = Path(dirpath)
        for filename in sorted(filenames):
            if exact_names is not None and filename not in exact_names:
                continue
            path = base / filename
            if suffixes is not None and path.suffix not in suffixes:
                continue
            yield path
