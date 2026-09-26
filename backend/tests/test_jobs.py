import asyncio

from btcintel.jobs.manager import JobManager


async def test_job_streams_events_then_result():
    jobs = JobManager()

    async def work(emit):
        emit({"type": "progress", "n": 1})
        await asyncio.sleep(0)
        emit({"type": "progress", "n": 2})
        return {"answer": 42}

    job = jobs.start("demo", work)
    events = [e async for e in jobs.stream(job.id)]
    assert [e["type"] for e in events] == ["progress", "progress", "status"]
    assert [e["seq"] for e in events] == [0, 1, 2]
    assert events[-1]["status"] == "done" and job.result == {"answer": 42}


async def test_failing_job_reports_error():
    jobs = JobManager()

    async def boom(emit):
        raise RuntimeError("bad")

    job = jobs.start("demo", boom)
    events = [e async for e in jobs.stream(job.id)]
    assert job.status == "error" and "RuntimeError: bad" in job.error and events[-1]["status"] == "error"


async def test_cancel_and_late_subscriber():
    jobs = JobManager()
    started = asyncio.Event()

    async def slow(emit):
        started.set()
        await asyncio.sleep(3600)

    job = jobs.start("slow", slow)
    await started.wait()
    assert jobs.cancel(job.id)
    events = [e async for e in jobs.stream(job.id)]
    assert job.status == "cancelled" and events[-1]["status"] == "cancelled"
    assert not jobs.cancel(job.id) and jobs.get("nope") is None


async def test_eviction_keeps_running_jobs():
    jobs = JobManager(max_jobs=2)

    async def quick(emit):
        return 1

    first = jobs.start("q", quick)
    await asyncio.sleep(0.01)
    jobs.start("q", quick)
    await asyncio.sleep(0.01)
    jobs.start("q", quick)
    assert jobs.get(first.id) is None and len(jobs.jobs) == 2
