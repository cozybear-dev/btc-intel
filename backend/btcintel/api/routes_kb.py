"""Knowledge base: catalog collections and Markdown pages (confined to docs/kb)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from btcintel.api.deps import rt
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")
COLLECTIONS = ("heuristics", "techniques", "incidents", "categories", "references")


@router.get("/kb/{collection}")
async def kb_collection(collection: str, s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="unknown collection")
    return [e.model_dump() for e in getattr(s.catalog, collection)]


@router.get("/kb-page")
async def kb_page(path: str, s: AppState = Depends(rt)) -> dict[str, str]:
    root = s.settings.kb_dir.resolve()
    page = (root / path).resolve()
    if not page.is_relative_to(root) or page.suffix != ".md":
        raise HTTPException(status_code=400, detail="path must be a .md file inside docs/kb")
    if not page.is_file():
        raise HTTPException(status_code=404, detail="no such page")
    return {"path": page.relative_to(root).as_posix(), "markdown": page.read_text(encoding="utf-8")}
