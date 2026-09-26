import httpx
import pytest
import respx

from btcintel.chain.budget import BudgetExceeded, CallBudget, budget_scope
from btcintel.chain.errors import NotFound, SourceError
from btcintel.chain.esplora import EsploraBackend
from btcintel.chain.ratelimit import TokenBucket
from btcintel.config import BackendConfig
from tests.fakes import FakeTime

BASE = "https://esplora.test/api"


@pytest.fixture
async def backend():
    ft = FakeTime()
    async with httpx.AsyncClient() as client:
        cfg = BackendConfig(name="t", base_url=BASE, rate_per_sec=100.0, burst=100,
                            headers={"Authorization": "Bearer tok"})
        bucket = TokenBucket(100.0, 100, clock=ft.clock, sleep=ft.sleep)
        yield EsploraBackend(cfg, client, bucket=bucket, sleep=ft.sleep), ft


@respx.mock
async def test_get_json_ok_and_headers_sent(backend):
    b, _ = backend
    route = respx.get(f"{BASE}/tx/abc").mock(return_value=httpx.Response(200, json={"txid": "abc"}))
    assert await b.get_json("/tx/abc") == {"txid": "abc"}
    assert route.call_count == 1
    assert route.calls[0].request.headers["Authorization"] == "Bearer tok"


@respx.mock
@pytest.mark.parametrize("status", [400, 404])
async def test_client_errors_are_not_found_without_retry(backend, status):
    b, _ = backend
    route = respx.get(f"{BASE}/tx/zz").mock(return_value=httpx.Response(status, text="nope"))
    with pytest.raises(NotFound):
        await b.get_json("/tx/zz")
    assert route.call_count == 1


@respx.mock
async def test_429_honours_retry_after(backend):
    b, ft = backend
    route = respx.get(f"{BASE}/x").mock(side_effect=[
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(200, json=[1]),
    ])
    assert await b.get_json("/x") == [1]
    assert route.call_count == 2
    assert ft.now >= 7


@respx.mock
async def test_5xx_retried_with_backoff_then_source_error(backend):
    b, ft = backend
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(503))
    with pytest.raises(SourceError, match="failed after 5 attempts"):
        await b.get_json("/x")
    assert route.call_count == 5
    assert ft.sleeps == [0.5, 1.0, 2.0, 4.0, 8.0]


@respx.mock
async def test_transport_error_is_retried(backend):
    b, _ = backend
    respx.get(f"{BASE}/blocks/tip/height").mock(side_effect=[
        httpx.ConnectError("boom"),
        httpx.Response(200, text="900000"),
    ])
    assert await b.get_text("/blocks/tip/height") == "900000"


@respx.mock
async def test_each_attempt_charges_the_budget(backend):
    b, _ = backend
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(503))
    with budget_scope(CallBudget(2)), pytest.raises(BudgetExceeded):
        await b.get_json("/x")
    assert route.call_count == 2


@respx.mock
async def test_unexpected_status_is_source_error(backend):
    b, _ = backend
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(418))
    with pytest.raises(SourceError, match="HTTP 418"):
        await b.get_json("/x")
    assert route.call_count == 1
