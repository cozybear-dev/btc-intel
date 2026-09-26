"""Automatic address analysis jobs."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from btcintel.analysis.models import AnalysisPolicy
from btcintel.analysis.run import analyze_address
from btcintel.api.deps import rt, valid_address
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")


class AnalyzeRequest(BaseModel):
    address: str
    depth: Literal["quick", "deep"] = "quick"


@router.post("/analyze", status_code=202)
async def start_analysis(req: AnalyzeRequest, s: AppState = Depends(rt)) -> dict[str, str]:
    address = valid_address(req.address)
    policy = AnalysisPolicy.deep() if req.depth == "deep" else AnalysisPolicy.quick()

    async def run(emit):
        report = await analyze_address(address, policy, chain=s.chain, tags=s.tags, uf=s.uf,
                                       taxonomy=s.taxonomy, emit=emit)
        return report.model_dump()

    return {"job_id": s.jobs.start("analysis", run).id}
