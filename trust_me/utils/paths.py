from __future__ import annotations

from datetime import datetime
from pathlib import Path


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
