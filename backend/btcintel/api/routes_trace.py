"""Tracing jobs, peel-chain following, job status and event streams."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from btcintel.api.deps import rt, valid_txid
from btcintel.chain.budget import CallBudget, budget_scope
from btcintel.runtime import AppState
from btcintel.trace.engine import TracePolicy, TraceSeed, trace
from btcintel.trace.peel import follow_peel_chain

router = APIRouter(prefix="/api")


class TraceRequest(BaseModel):
    seed: TraceSeed
    policy: TracePolicy = TracePolicy()


class PeelRequest(BaseModel):
    txid: str
    max_steps: int = Field(50, ge=1, le=500)


@router.post("/trace", status_code=202)
async def start_trace(req: TraceRequest, s: AppState = Depends(rt)) -> dict[str, str]:
    labels = s.labels(req.policy.stop_categories)

    async def run(emit):
        return (await trace(req.seed, req.policy, chain=s.chain, labels=labels, emit=emit)).model_dump()

    return {"job_id": s.jobs.start("trace", run).id}


@router.post("/peel")
async def peel(req: PeelRequest, s: AppState = Depends(rt)) -> dict[str, Any]:
    txid = valid_txid(req.txid)
    with budget_scope(CallBudget(req.max_steps * 2 + 10)):
        result = await follow_peel_chain(txid, s.chain, s.labels(), max_steps=req.max_steps)
    return result.model_dump()


def _job_or_404(s: AppState, job_id: str):
    job = s.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return job


@router.get("/jobs/{job_id}")
async def job_status(job_id: str, s: AppState = Depends(rt)) -> dict[str, Any]:
    job = _job_or_404(s, job_id)
    return {"id": job.id, "kind": job.kind, "status": job.status, "error": job.error,
            "events": len(job.events), "result": job.result if job.status == "done" else None}


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request, since: int = 0, s: AppState = Depends(rt)):
    _job_or_404(s, job_id)

    async def gen():
        async for event in s.jobs.stream(job_id, start=since):
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str, s: AppState = Depends(rt)) -> dict[str, bool]:
    _job_or_404(s, job_id)
    return {"cancelled": s.jobs.cancel(job_id)}
