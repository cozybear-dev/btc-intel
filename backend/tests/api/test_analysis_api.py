import json

from tests.analysis_scenario import A, build_funded, ransomware_tag
from tests.api.conftest import wait_job
from tests.fakes import FakeChain


def test_analyze_job_streams_sections_and_returns_the_report(make_client):
    client = make_client(FakeChain(build_funded().txs))
    client.app.state.rt.tags.add_many([ransomware_tag()])
    r = client.post("/api/analyze", json={"address": A.upper()})
    assert r.status_code == 202
    job = wait_job(client, r.json()["job_id"])
    assert job["status"] == "done" and job["kind"] == "analysis"
    result = job["result"]
    assert result["address"] == A and result["depth"] == "quick"
    assert result["verdict"]["level"] == "severe" and result["markdown"].startswith(f"# Address analysis: {A}")
    with client.stream("GET", f"/api/jobs/{job['id']}/events") as stream:
        events = [json.loads(line[6:]) for line in stream.iter_lines() if line.startswith("data: ")]
    names = [e["name"] for e in events if e["type"] == "section"]
    assert names[0] == "profile" and names[-1] == "verdict"
    assert events[-2]["type"] == "done"
    assert events[-1] == {"seq": len(events) - 1, "type": "status", "status": "done", "error": None}


def test_analyze_rejects_bad_input(client):
    assert client.post("/api/analyze", json={"address": "nope"}).status_code == 400
    assert client.post("/api/analyze", json={"address": A, "depth": "huge"}).status_code == 422
