import pytest
from fastapi.testclient import TestClient

from btcintel.api.app import create_app
from btcintel.config import load_settings
from tests.fakes import FakeChain
from tests.scenario import build_scenario, scenario_tags


@pytest.fixture
def scenario():
    return build_scenario()


@pytest.fixture
def make_client(tmp_path, scenario):
    clients = []

    def _make(chain=None, env=None) -> TestClient:
        settings = load_settings({"BTCINTEL_DATA_DIR": str(tmp_path / f"data{len(clients)}"), **(env or {})})
        app = create_app(settings, chain=chain or FakeChain(scenario.txs))
        client = TestClient(app, base_url="http://127.0.0.1")  # the API only answers loopback Host headers
        client.__enter__()
        app.state.rt.tags.add_many(scenario_tags())
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()


def wait_job(client, job_id, timeout=5.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] != "running":
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")
