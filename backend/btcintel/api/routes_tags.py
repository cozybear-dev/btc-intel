"""Attribution tags: lookup, search, analyst tags, TagPack export/import."""

from __future__ import annotations

from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from btcintel.api.deps import rt, valid_address
from btcintel.labels.importers import import_tagpack_text
from btcintel.labels.store import CONFIDENCE_LEVELS, Tag
from btcintel.labels.tagpack import export_tagpack
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")


class NewTag(BaseModel):
    address: str
    label: str = Field(min_length=1, max_length=200)
    category: str
    abuse: str | None = None
    actor: str | None = Field(None, max_length=200)
    source: str = Field("analyst", max_length=500)
    confidence: str = "forensic_investigation"


class ImportRequest(BaseModel):
    pack: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    yaml: str = Field(max_length=20_000_000)


@router.get("/tags")
async def tags_for_address(address: str, s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    return [t.model_dump() for t in s.tags.for_address(valid_address(address))]


@router.get("/tags/search")
async def search_tags(q: str, limit: int = Query(50, ge=1, le=500), s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    return [t.model_dump() for t in s.tags.search(q, limit)]


@router.get("/tags/packs")
async def packs(s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    return [{"pack": p, "count": n} for p, n in s.tags.packs()]


@router.post("/tags", status_code=201)
async def add_tag(body: NewTag, s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(body.address)
    if body.category not in s.taxonomy.categories:
        raise HTTPException(status_code=400, detail=f"unknown category {body.category!r}")
    if body.abuse is not None and body.abuse not in s.taxonomy.categories:
        raise HTTPException(status_code=400, detail=f"unknown abuse category {body.abuse!r}")
    if body.confidence not in CONFIDENCE_LEVELS:
        raise HTTPException(status_code=400, detail=f"unknown confidence {body.confidence!r}")
    tag = Tag(address=address, label=body.label, category=body.category, abuse=body.abuse, actor=body.actor,
              confidence=body.confidence, source=body.source, pack="user", created_by="analyst")
    stored = s.tags.get(s.tags.add(tag))
    return stored.model_dump() if stored else tag.model_dump()


@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(tag_id: int, s: AppState = Depends(rt)) -> Response:
    if not s.tags.delete(tag_id):
        raise HTTPException(status_code=404, detail="unknown tag")
    return Response(status_code=204)


@router.get("/tags/export", response_class=PlainTextResponse)
async def export(pack: str = "user", s: AppState = Depends(rt)) -> PlainTextResponse:
    text = export_tagpack(s.tags.by_pack(pack), title=f"btc-intel {pack} tags", creator="btc-intel")
    return PlainTextResponse(text, media_type="application/yaml")


@router.post("/tags/import")
async def import_tags(body: ImportRequest, s: AppState = Depends(rt)) -> dict[str, Any]:
    try:
        report = import_tagpack_text(s.tags, s.taxonomy, body.yaml, body.pack)
    except (ValueError, yaml.YAMLError) as e:
        raise HTTPException(status_code=400, detail=f"invalid TagPack: {e}") from e
    return {"tags": report.tags, "warnings": report.warnings[:100]}
