"""In-process background jobs with replayable event streams (for SSE)."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

Emit = Callable[[dict[str, Any]], None]


@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    task: asyncio.Task[Any] | None = None
    changed: asyncio.Event = field(default_factory=asyncio.Event)

    def push(self, event: dict[str, Any]) -> None:
        self.events.append({"seq": len(self.events), **event})
        self.changed.set()


class JobManager:
    def __init__(self, max_jobs: int = 200) -> None:
        self.max_jobs = max_jobs
        self.jobs: OrderedDict[str, Job] = OrderedDict()

    def start(self, kind: str, fn: Callable[[Emit], Awaitable[Any]]) -> Job:
        job = Job(id=uuid.uuid4().hex, kind=kind)

        async def runner() -> None:
            try:
                job.result = await fn(job.push)
                job.status = "done"
            except asyncio.CancelledError:
                job.status = "cancelled"
            except Exception as e:  # noqa: BLE001 - surfaced to the client
                job.status = "error"
                job.error = f"{type(e).__name__}: {e}"
            finally:
                job.push({"type": "status", "status": job.status, "error": job.error})

        job.task = asyncio.get_running_loop().create_task(runner())
        self.jobs[job.id] = job
        self._evict()
        return job

    def _evict(self) -> None:
        for jid in list(self.jobs):
            if len(self.jobs) <= self.max_jobs:
                break
            if self.jobs[jid].status != "running":
                del self.jobs[jid]

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job is None or job.task is None or job.task.done():
            return False
        job.task.cancel()
        return True

    async def stream(self, job_id: str, start: int = 0) -> AsyncIterator[dict[str, Any]]:
        job = self.jobs[job_id]
        i = start
        while True:
            while i < len(job.events):
                yield job.events[i]
                i += 1
            if job.status != "running":  # the final status event is pushed in the same step
                return
            job.changed.clear()
            if i < len(job.events):
                continue
            await job.changed.wait()
