"""Runtime settings, read from BTCINTEL_* environment variables."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from btcintel.paths import REPO_ROOT

DEFAULT_BACKENDS = "mempool=https://mempool.space/api@1+price,blockstream=https://blockstream.info/api@4"


@dataclass(frozen=True)
class BackendConfig:
    name: str
    base_url: str
    rate_per_sec: float
    burst: int = 1
    supports_price: bool = False
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    catalog_dir: Path
    kb_dir: Path
    backends: tuple[BackendConfig, ...]
    proxy: str | None = None
    host: str = "127.0.0.1"
    port: int = 8765
    allowed_hosts: tuple[str, ...] = ()  # Host headers the API answers; empty = derive from host

    @property
    def cache_path(self) -> Path:
        return self.data_dir / "cache.db"

    @property
    def intel_path(self) -> Path:
        return self.data_dir / "intel.db"


def parse_backends(spec: str) -> tuple[BackendConfig, ...]:
    """Parse 'name=url@rate[+price],...' (rate = requests/second)."""
    backends = []
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        name, sep, rest = part.partition("=")
        url, at, rate_s = rest.rpartition("@")
        if not sep or not at or not name or not url:
            raise ValueError(f"backend {part!r}: expected name=url@rate[+price]")
        supports_price = rate_s.endswith("+price")
        try:
            rate = float(rate_s.removesuffix("+price"))
        except ValueError as e:
            raise ValueError(f"backend {part!r}: rate must be a number") from e
        if rate <= 0:
            raise ValueError(f"backend {part!r}: rate must be positive")
        backends.append(
            BackendConfig(
                name=name.strip(), base_url=url.strip().rstrip("/"), rate_per_sec=rate,
                burst=max(1, math.floor(rate)), supports_price=supports_price,
            )
        )
    if not backends:
        raise ValueError("no chain backends configured")
    return tuple(backends)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    return Settings(
        data_dir=Path(env.get("BTCINTEL_DATA_DIR", str(REPO_ROOT / "data"))),
        catalog_dir=Path(env.get("BTCINTEL_CATALOG_DIR", str(REPO_ROOT / "catalog"))),
        kb_dir=Path(env.get("BTCINTEL_KB_DIR", str(REPO_ROOT / "docs" / "kb"))),
        backends=parse_backends(env.get("BTCINTEL_BACKENDS") or DEFAULT_BACKENDS),
        proxy=env.get("BTCINTEL_PROXY") or None,
        host=env.get("BTCINTEL_HOST", "127.0.0.1"),
        port=int(env.get("BTCINTEL_PORT", "8765")),
        allowed_hosts=tuple(h for h in (p.strip() for p in env.get("BTCINTEL_ALLOWED_HOSTS", "").split(",")) if h),
    )
