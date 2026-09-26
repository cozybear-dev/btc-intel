"""Network checks for the catalog: reference URLs resolve, incident seeds exist on chain."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Iterable

from btcintel.catalog.schema import Catalog

_UA = {"User-Agent": "btc-intel-catalog-check/0.1 (+https://github.com)"}


def _status(url: str, timeout: float) -> int | str:
    req = urllib.request.Request(url, headers=_UA, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return f"unreachable: {e}"


def check_urls(urls: Iterable[str], timeout: float = 20.0) -> list[tuple[str, str]]:
    problems = []
    for url in urls:
        status = _status(url, timeout)
        if isinstance(status, str) or status >= 400:
            problems.append((url, status if isinstance(status, str) else f"HTTP {status}"))
    return problems


def verify_seeds(
    cat: Catalog, base_url: str = "https://mempool.space/api", delay: float = 1.0
) -> list[tuple[str, str]]:
    """Every seed address/txid must be known to an Esplora API (1 request per `delay` seconds)."""
    problems = []
    for inc in cat.incidents:
        for seed in inc.seeds:
            path = f"/address/{seed.value}" if seed.kind == "address" else f"/tx/{seed.value}"
            status = _status(base_url + path, timeout=20.0)
            if status != 200:
                problems.append((f"{inc.id} {seed.kind} {seed.value}", str(status)))
            time.sleep(delay)
    return problems
