"""Well-known repository paths (overridable via environment variables)."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def catalog_dir() -> Path:
    return Path(os.environ.get("BTCINTEL_CATALOG_DIR", REPO_ROOT / "catalog"))


def kb_dir() -> Path:
    return Path(os.environ.get("BTCINTEL_KB_DIR", REPO_ROOT / "docs" / "kb"))
