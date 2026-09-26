"""Case files: CRUD and watchlists."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from btcintel.api.deps import rt, valid_address
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")


class CaseBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    notes: str = ""
    graph: dict[str, Any] | None = None


class CaseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    notes: str | None = None
    graph: dict[str, Any] | None = None


class WatchBody(BaseModel):
    address: str


def _case_or_404(s: AppState, case_id: str):
    case = s.cases.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="unknown case")
    return case


@router.get("/cases")
async def list_cases(s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    return [c.model_dump() for c in s.cases.list()]


@router.post("/cases", status_code=201)
async def create_case(body: CaseBody, s: AppState = Depends(rt)) -> dict[str, Any]:
    try:
        return s.cases.create(body.name, body.notes, body.graph).model_dump()
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e


@router.get("/cases/{case_id}")
async def get_case(case_id: str, s: AppState = Depends(rt)) -> dict[str, Any]:
    return _case_or_404(s, case_id).model_dump()


@router.put("/cases/{case_id}")
async def update_case(case_id: str, body: CaseUpdate, s: AppState = Depends(rt)) -> dict[str, Any]:
    try:
        case = s.cases.update(case_id, name=body.name, notes=body.notes, graph=body.graph)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    if case is None:
        raise HTTPException(status_code=404, detail="unknown case")
    return case.model_dump()


@router.delete("/cases/{case_id}", status_code=204)
async def delete_case(case_id: str, s: AppState = Depends(rt)) -> Response:
    if not s.cases.delete(case_id):
        raise HTTPException(status_code=404, detail="unknown case")
    return Response(status_code=204)


@router.post("/cases/{case_id}/watch")
async def watch(case_id: str, body: WatchBody, s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(body.address)
    _case_or_404(s, case_id)
    s.cases.watch(case_id, address)
    return _case_or_404(s, case_id).model_dump()


@router.delete("/cases/{case_id}/watch/{address}")
async def unwatch(case_id: str, address: str, s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(address)
    _case_or_404(s, case_id)
    s.cases.unwatch(case_id, address)
    return _case_or_404(s, case_id).model_dump()
