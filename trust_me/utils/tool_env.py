from __future__ import annotations

import tempfile
from pathlib import Path


def go_tool_env() -> dict[str, str]:
    base = Path(tempfile.gettempdir()) / "trust_me_go"
    gocache = base / "build-cache"
    gopath = base / "gopath"
    gocache.mkdir(parents=True, exist_ok=True)
    gopath.mkdir(parents=True, exist_ok=True)
    return {
        "GOCACHE": str(gocache),
        "GOPATH": str(gopath),
    }
