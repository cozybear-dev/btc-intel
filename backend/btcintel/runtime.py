"""Wire settings → chain source, intel database, stores, catalog. Shared by the API and the CLI."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

from btcintel import __version__
from btcintel.cases.store import CaseStore
from btcintel.catalog.loader import load_catalog
from btcintel.catalog.schema import Catalog
from btcintel.chain.cache import Cache
from btcintel.chain.client import ChainClient
from btcintel.chain.esplora import EsploraBackend
from btcintel.chain.source import ChainSource
from btcintel.cluster.unionfind import UnionFind
from btcintel.config import Settings
from btcintel.db import open_intel_db
from btcintel.heuristics.base import Context
from btcintel.jobs.manager import JobManager
from btcintel.labels.lookup import LabelLookup
from btcintel.labels.store import TagStore
from btcintel.labels.taxonomy import Taxonomy


@dataclass
class AppState:
    settings: Settings
    chain: ChainSource
    conn: sqlite3.Connection
    tags: TagStore
    uf: UnionFind
    cases: CaseStore
    jobs: JobManager
    catalog: Catalog
    taxonomy: Taxonomy

    def labels(self, stop_categories: Iterable[str] | None = None) -> LabelLookup:
        return LabelLookup(self.tags, self.taxonomy, self.uf, stop_categories)

    def context(self) -> Context:
        return Context(chain=self.chain, coinbase_rules=self.tags.coinbase_rules())


@asynccontextmanager
async def open_runtime(settings: Settings, chain: ChainSource | None = None) -> AsyncIterator[AppState]:
    http: httpx.AsyncClient | None = None
    cache: Cache | None = None
    if chain is None:
        http = httpx.AsyncClient(
            proxy=settings.proxy, timeout=httpx.Timeout(20.0, connect=10.0), follow_redirects=True,
            headers={"User-Agent": f"btc-intel/{__version__}"},
        )
        cache = Cache(settings.cache_path)
        chain = ChainClient([EsploraBackend(b, http) for b in settings.backends], cache)
    conn = open_intel_db(settings.intel_path)
    catalog = load_catalog(settings.catalog_dir)
    try:
        yield AppState(settings=settings, chain=chain, conn=conn, tags=TagStore(conn), uf=UnionFind(conn),
                       cases=CaseStore(conn), jobs=JobManager(), catalog=catalog,
                       taxonomy=Taxonomy.from_catalog(catalog))
    finally:
        if http is not None:
            await http.aclose()
        if cache is not None:
            cache.close()
        conn.close()
