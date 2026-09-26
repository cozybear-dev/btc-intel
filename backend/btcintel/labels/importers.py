"""Download-and-import helpers used by the CLI and API."""

from __future__ import annotations

import io
import tarfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

import httpx
import yaml

from btcintel.labels.ofac import OFAC_SDN_URL, parse_sdn_xml
from btcintel.labels.pools import POOLS_URL, parse_pools
from btcintel.labels.ransomwhere import RANSOMWHERE_URL, parse_ransomwhere
from btcintel.labels.store import TagStore
from btcintel.labels.tagpack import parse_tagpack
from btcintel.labels.taxonomy import Taxonomy

GRAPHSENSE_TARBALL_URL = "https://codeload.github.com/graphsense/graphsense-tagpacks/tar.gz/refs/heads/master"

__all__ = [
    "GRAPHSENSE_TARBALL_URL", "OFAC_SDN_URL", "POOLS_URL", "RANSOMWHERE_URL", "ImportReport",
    "fetch", "import_graphsense_tarball", "import_ofac", "import_pools", "import_ransomwhere",
    "import_tagpack_text",
]


@dataclass
class ImportReport:
    packs: int = 0
    tags: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def fetch(url: str, proxy: str | None = None, timeout: float = 300.0) -> bytes:
    resp = httpx.get(url, proxy=proxy, timeout=timeout, follow_redirects=True,
                     # identity: some sources (api.ransomwhe.re) answer 502 when compression is offered
                     headers={"User-Agent": "btc-intel-importer/0.1", "Accept-Encoding": "identity"})
    resp.raise_for_status()
    return resp.content


def import_tagpack_text(store: TagStore, taxonomy: Taxonomy, text: str, pack: str) -> ImportReport:
    tags, warnings = parse_tagpack(text, pack, taxonomy)
    store.delete_pack(pack)
    return ImportReport(packs=1, tags=store.add_many(tags), warnings=warnings)


def import_graphsense_tarball(store: TagStore, taxonomy: Taxonomy, data: bytes) -> ImportReport:
    """Import every packs/*.yaml from a GraphSense TagPacks tarball (read in memory, never extracted)."""
    report = ImportReport()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if not member.isfile() or "packs" not in path.parts or path.suffix != ".yaml":
                continue
            pack = f"gs:{path.stem}"
            text = tar.extractfile(member).read().decode("utf-8", errors="replace")  # type: ignore[union-attr]
            report.packs += 1
            try:
                sub = import_tagpack_text(store, taxonomy, text, pack)
            except (ValueError, yaml.YAMLError) as e:
                report.errors.append(f"{pack}: {e}")
                continue
            report.tags += sub.tags
            report.warnings += sub.warnings
    return report


def import_ofac(store: TagStore, data: bytes) -> ImportReport:
    tags, _ = parse_sdn_xml(io.BytesIO(data))
    store.delete_pack("ofac_sdn")
    return ImportReport(packs=1, tags=store.add_many(tags))


def import_pools(store: TagStore, data: bytes) -> ImportReport:
    tags, rules = parse_pools(data.decode())
    store.delete_pack("mempool_pools")
    report = ImportReport(packs=1, tags=store.add_many(tags))
    store.set_coinbase_rules(rules)
    return report


def import_ransomwhere(store: TagStore, data: bytes) -> ImportReport:
    tags = parse_ransomwhere(data.decode())
    store.delete_pack("ransomwhere")
    return ImportReport(packs=1, tags=store.add_many(tags))
