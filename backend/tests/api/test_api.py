from btcintel import __version__
from tests.api.conftest import wait_job
from tests.builders import ADDR
from tests.fakes import FakeChain
from tests.scenario import EX, H1, V


def test_health_and_search(client, scenario):
    assert client.get("/api/health").json() == {"status": "ok", "version": __version__}
    assert client.get("/api/search", params={"q": scenario.theft.txid.upper()}).json() == {
        "kind": "txid", "query": scenario.theft.txid}
    body = client.get("/api/search", params={"q": "example exchange"}).json()
    assert body["kind"] == "text" and body["tags"][0]["address"] == EX


def test_tx_endpoint(client, scenario):
    body = client.get(f"/api/tx/{scenario.theft.txid}").json()
    assert body["tx"]["txid"] == scenario.theft.txid and body["price_usd"] is None
    assert any(f["heuristic"] == "H-FP" for f in body["findings"])
    assert set(body["addresses"]) >= {V, H1} and body["flags"] == []
    assert client.get(f"/api/tx/{scenario.theft.txid}/outspends").json()[0]["spent"] is True


def test_invalid_ids_return_400(client):
    assert client.get("/api/tx/xyz").status_code == 400
    assert client.get("/api/address/notanaddress").status_code == 400
    assert client.get("/api/address/" + ADDR[0] + "/txs", params={"after": "zz"}).status_code == 400


def test_unknown_tx_is_404(client):
    assert client.get("/api/tx/" + "ab" * 32).status_code == 404


def test_backend_failure_is_502(make_client, scenario):
    c = make_client(FakeChain(scenario.txs, fail_on={scenario.t1.txid}))
    r = c.get(f"/api/tx/{scenario.t1.txid}")
    assert r.status_code == 502 and r.json()["incomplete"] is True


def test_uppercase_bech32_address_is_normalised(client):
    body = client.get(f"/api/address/{H1.upper()}").json()
    assert body["stats"]["address"] == H1 and body["info"]["address"] == H1
    page = client.get(f"/api/address/{H1}/txs").json()
    assert page["txs"][0]["delta"] == 600_000 and page["next"]


def test_trace_job_and_event_stream(client, scenario):
    r = client.post("/api/trace", json={"seed": {"txid": scenario.theft.txid}, "policy": {"max_hops": 4}})
    assert r.status_code == 202
    job = wait_job(client, r.json()["job_id"])
    assert job["status"] == "done" and not job["result"]["incomplete"]
    assert {s["reason"] for s in job["result"]["stops"]} >= {"labeled", "unspent"}
    with client.stream("GET", f"/api/jobs/{job['id']}/events") as stream:
        lines = [line for line in stream.iter_lines() if line.startswith("data: ")]
    assert '"type": "done"' in lines[-2] and '"status": "done"' in lines[-1]
    assert client.post("/api/trace", json={"seed": {"txid": "zz"}}).status_code == 422
    assert client.get("/api/jobs/nope").status_code == 404


def test_peel_endpoint(client, scenario):
    body = client.post("/api/peel", json={"txid": scenario.t1.txid}).json()
    assert body["start_txid"] == scenario.t1.txid and body["end_reason"] in {"unspent", "not_peel_shaped", "labeled"}


def test_cluster_expand_and_get(client, scenario):
    job = wait_job(client, client.post(f"/api/cluster/{V}/expand", json={"max_calls": 50}).json()["job_id"])
    assert job["status"] == "done" and job["result"]["root"] == V
    body = client.get(f"/api/cluster/{V}").json()
    assert body["root"] == V and V in body["members"]
    assert client.get(f"/api/cluster/{ADDR[14]}").json() == {"root": None, "address": ADDR[14]}


def test_tags_crud_export_import(client):
    r = client.post("/api/tags", json={"address": ADDR[6].upper(), "label": "Suspect", "category": "perpetrator",
                                       "abuse": "theft"})
    assert r.status_code == 201 and r.json()["address"] == ADDR[6] and r.json()["pack"] == "user"
    assert client.post("/api/tags", json={"address": ADDR[6], "label": "x", "category": "nope"}).status_code == 400
    assert client.get("/api/tags", params={"address": ADDR[6]}).json()[0]["label"] == "Suspect"
    exported = client.get("/api/tags/export", params={"pack": "user"}).text
    assert "Suspect" in exported
    imported = client.post("/api/tags/import", json={"pack": "roundtrip", "yaml": exported}).json()
    assert imported["tags"] == 1
    assert client.post("/api/tags/import", json={"pack": "bad", "yaml": "tags: [oops"}).status_code == 400
    assert {"pack": "roundtrip", "count": 1} in client.get("/api/tags/packs").json()
    tag_id = r.json()["id"]
    assert client.delete(f"/api/tags/{tag_id}").status_code == 204
    assert client.delete(f"/api/tags/{tag_id}").status_code == 404


def test_cases_crud(client):
    case = client.post("/api/cases", json={"name": "Investigation"}).json()
    assert client.get("/api/cases").json()[0]["id"] == case["id"]
    updated = client.put(f"/api/cases/{case['id']}", json={"notes": "n", "graph": {"nodes": [1]}}).json()
    assert updated["notes"] == "n" and updated["graph"] == {"nodes": [1]}
    watched = client.post(f"/api/cases/{case['id']}/watch", json={"address": ADDR[1]}).json()
    assert watched["watch"] == [ADDR[1]]
    assert client.delete(f"/api/cases/{case['id']}/watch/{ADDR[1]}").json()["watch"] == []
    assert client.post(f"/api/cases/{case['id']}/watch", json={"address": "bad"}).status_code == 400
    assert client.delete(f"/api/cases/{case['id']}").status_code == 204
    assert client.get(f"/api/cases/{case['id']}").status_code == 404


def test_kb_endpoints(client):
    heuristics = client.get("/api/kb/heuristics").json()
    assert any(h["id"] == "H-CIOH" for h in heuristics)
    assert client.get("/api/kb/nope").status_code == 404
    page = client.get("/api/kb-page", params={"path": "heuristics/h-cioh.md"}).json()
    assert page["markdown"].startswith("# H-CIOH")


def test_kb_page_rejects_traversal(client):
    assert client.get("/api/kb-page", params={"path": "../../README.md"}).status_code == 400
    assert client.get("/api/kb-page", params={"path": "heuristics/missing.md"}).status_code == 404
    assert client.get("/api/kb-page", params={"path": "../../backend/pyproject.toml"}).status_code == 400
