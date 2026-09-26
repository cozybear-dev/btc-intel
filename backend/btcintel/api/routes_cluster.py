"""Cluster inspection and expansion jobs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from btcintel.api.deps import rt, valid_address
from btcintel.cluster.expand import ExpandPolicy, cluster_conflicts, cluster_tags, expand_cluster
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")


@router.get("/cluster/{address}")
async def get_cluster(address: str, limit: int = Query(500, ge=1, le=10_000),
                      s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(address)
    root = s.uf.root_of(address)
    if root is None:
        return {"root": None, "address": address}
    meta = s.uf.meta(root)
    return {"root": root, "meta": meta.model_dump() if meta else None, "members": s.uf.members(root, limit),
            "tags": [t.model_dump() for t in cluster_tags(root, s.uf, s.tags)[:200]],
            "conflicts": [c.model_dump() for c in cluster_conflicts(root, s.uf, s.tags)],
            "links": s.uf.links(root)}


@router.post("/cluster/{address}/expand", status_code=202)
async def expand(address: str, policy: ExpandPolicy | None = None, s: AppState = Depends(rt)) -> dict[str, str]:
    address = valid_address(address)

    async def run(emit):
        result = await expand_cluster(address, s.chain, s.uf, s.tags, policy or ExpandPolicy(), progress=emit)
        return result.model_dump()

    return {"job_id": s.jobs.start("cluster", run).id}
