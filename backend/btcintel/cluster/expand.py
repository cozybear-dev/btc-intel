"""Capped cluster expansion: walk address histories and union co-spent inputs (H-CIOH)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import aclosing
from typing import Any

from pydantic import BaseModel, Field

from btcintel.chain.budget import BudgetExceeded, CallBudget, budget_scope
from btcintel.chain.errors import SourceError
from btcintel.chain.source import ChainSource
from btcintel.chain.validate import normalize_address
from btcintel.cluster.unionfind import UnionFind
from btcintel.heuristics.cioh import cioh_addresses
from btcintel.labels.store import Tag, TagStore

ENTITY_MIN_CONFIDENCE = 50
NON_ENTITY_CATEGORIES = {"unknown", "victim", "individual", "organization", "perpetrator"}

Progress = Callable[[dict[str, Any]], None]


class ExpandPolicy(BaseModel):
    max_addresses: int = Field(2000, ge=1, le=100_000)
    max_calls: int = Field(400, ge=1, le=20_000)
    max_txs_per_address: int = Field(200, ge=1, le=10_000)


class Conflict(BaseModel):
    labels: list[str]
    addresses: list[str]


class ExpandResult(BaseModel):
    root: str
    size: int
    partial: bool
    capped: bool
    calls_used: int
    new_links: int
    conflicts: list[Conflict]


def cluster_tags(root: str, uf: UnionFind, tags: TagStore, limit: int = 10_000) -> list[Tag]:
    by_address = tags.for_addresses(uf.members(root, limit))
    return sorted((t for ts in by_address.values() for t in ts),
                  key=lambda t: (-t.confidence_level, t.label))


def cluster_conflicts(root: str, uf: UnionFind, tags: TagStore) -> list[Conflict]:
    names: dict[str, set[str]] = defaultdict(set)
    for t in cluster_tags(root, uf, tags):
        if t.confidence_level < ENTITY_MIN_CONFIDENCE or t.category in NON_ENTITY_CATEGORIES:
            continue
        names[(t.actor or t.label).strip().lower()].add(t.address)
    if len(names) <= 1:
        return []
    addresses = sorted({a for group in names.values() for a in group})[:50]
    return [Conflict(labels=sorted(names), addresses=addresses)]


async def expand_cluster(
    seed: str,
    chain: ChainSource,
    uf: UnionFind,
    tags: TagStore,
    policy: ExpandPolicy | None = None,
    progress: Progress | None = None,
) -> ExpandResult:
    policy = policy or ExpandPolicy()
    seed = normalize_address(seed)
    budget = CallBudget(policy.max_calls)
    queue = deque(uf.members(uf.find(seed)))
    visited: set[str] = set()
    new_links = 0
    partial = capped = False
    with budget_scope(budget):
        try:
            while queue and not capped:
                address = queue.popleft()
                if address in visited:
                    continue
                visited.add(address)
                seen = 0
                async with aclosing(chain.iter_address_txs(address, policy.max_txs_per_address)) as txs:
                    async for tx in txs:
                        seen += 1
                        linked = cioh_addresses(tx)
                        if not linked or address not in linked:
                            continue
                        for other in linked:
                            if uf.find(other) != uf.find(address):
                                uf.union(address, other, txid=tx.txid, heuristic="H-CIOH")
                                new_links += 1
                            if other not in visited:
                                queue.append(other)
                        if uf.size(uf.find(seed)) >= policy.max_addresses:
                            capped = True
                            break
                if seen >= policy.max_txs_per_address:
                    partial = True
                if progress:
                    progress({"type": "progress", "visited": len(visited), "queued": len(queue),
                              "size": uf.size(uf.find(seed)), "calls": budget.used})
        except (BudgetExceeded, SourceError):
            partial = True
    if capped or any(a not in visited for a in queue):
        partial = True
    root = uf.find(seed)
    uf.set_meta(root, partial=partial, capped=capped, calls_used_add=budget.used, expanded_at=time.time())
    return ExpandResult(root=root, size=uf.size(root), partial=partial, capped=capped,
                        calls_used=budget.used, new_links=new_links,
                        conflicts=cluster_conflicts(root, uf, tags))
