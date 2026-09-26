import copy
import json
from pathlib import Path

import httpx
import pytest

from btcintel.chain.cache import Cache
from btcintel.chain.client import ChainClient
from btcintel.chain.errors import NotFound, SourceError
from btcintel.chain.esplora import EsploraBackend
from btcintel.chain.ratelimit import TokenBucket
from btcintel.config import BackendConfig
from tests.fakes import FakeTime

A = "https://a.test/api"
B = "https://b.test/api"
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "esplora"
TXID = "c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c"


def fixture_tx(txid: str = TXID, confirmed: bool = True, height: int = 900000) -> dict:
    d = copy.deepcopy(json.loads((FIX / "tx_c5908e04.json").read_text()))
    d["txid"] = txid
    d["status"] = {"confirmed": confirmed, "block_height": height if confirmed else None,
                   "block_hash": "00" * 32 if confirmed else None,
                   "block_time": 1749188499 if confirmed else None}
    return d


@pytest.fixture
async def make_client(tmp_path):
    http = httpx.AsyncClient()
    now = [1_000_000.0]
    ft = FakeTime()

    def _make() -> ChainClient:
        def backend(name: str, base: str, price: bool) -> EsploraBackend:
            cfg = BackendConfig(name=name, base_url=base, rate_per_sec=100.0, burst=100, supports_price=price)
            return EsploraBackend(cfg, http, bucket=TokenBucket(100.0, 100, clock=ft.clock, sleep=ft.sleep),
                                  sleep=ft.sleep)
        cache = Cache(tmp_path / "cache.db", clock=lambda: now[0])
        return ChainClient([backend("a", A, True), backend("b", B, False)], cache)

    _make.now = now  # type: ignore[attr-defined]
    yield _make
    await http.aclose()


@pytest.mark.respx(assert_all_called=False)
async def test_deep_tx_is_cached_forever(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    route = respx_mock.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx()))
    first = await client.get_tx(TXID)
    make_client.now[0] += 10 * 86400
    second = await client.get_tx(TXID)
    assert first == second and route.call_count == 1


@pytest.mark.respx(assert_all_called=False)
async def test_unconfirmed_tx_uses_short_ttl(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    route = respx_mock.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx(confirmed=False)))
    await client.get_tx(TXID)
    await client.get_tx(TXID)
    assert route.call_count == 1
    make_client.now[0] += 61
    await client.get_tx(TXID)
    assert route.call_count == 2


@pytest.mark.respx(assert_all_called=False)
async def test_shallow_confirmed_tx_uses_short_ttl(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900002"))
    route = respx_mock.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx(height=900000)))
    await client.get_tx(TXID)
    make_client.now[0] += 61
    await client.get_tx(TXID)
    assert route.call_count == 2


@pytest.mark.respx(assert_all_called=False)
async def test_failover_to_second_backend(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    respx_mock.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(503))
    b_route = respx_mock.get(f"{B}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx()))
    tx = await client.get_tx(TXID)
    assert tx.txid == TXID and b_route.call_count == 1


@pytest.mark.respx(assert_all_called=False)
async def test_not_found_does_not_fail_over(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(404, text="Transaction not found"))
    b_route = respx_mock.get(f"{B}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx()))
    with pytest.raises(NotFound):
        await client.get_tx(TXID)
    assert b_route.call_count == 0


@pytest.mark.respx(assert_all_called=False)
async def test_all_backends_failing_raises_source_error(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(503))
    respx_mock.get(f"{B}/tx/{TXID}").mock(return_value=httpx.Response(503))
    with pytest.raises(SourceError, match="all backends failed"):
        await client.get_tx(TXID)


@pytest.mark.respx(assert_all_called=False)
async def test_tip_height_is_cached(make_client, respx_mock):
    client = make_client()
    route = respx_mock.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100\n"))
    assert await client.tip_height() == 900100
    assert await client.tip_height() == 900100
    assert route.call_count == 1


@pytest.mark.respx(assert_all_called=False)
async def test_outspends_all_spent_deep_cached_forever(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    body = [{"spent": True, "txid": "ab" * 32, "vin": 0,
             "status": {"confirmed": True, "block_height": 900001}}]
    route = respx_mock.get(f"{A}/tx/{TXID}/outspends").mock(return_value=httpx.Response(200, json=body))
    await client.get_outspends(TXID)
    make_client.now[0] += 86400
    spends = await client.get_outspends(TXID)
    assert spends[0].spent and route.call_count == 1


@pytest.mark.respx(assert_all_called=False)
async def test_outspends_with_unspent_output_use_short_ttl(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    route = respx_mock.get(f"{A}/tx/{TXID}/outspends").mock(return_value=httpx.Response(200, json=[{"spent": False}]))
    await client.get_outspends(TXID)
    make_client.now[0] += 121
    await client.get_outspends(TXID)
    assert route.call_count == 2


@pytest.mark.respx(assert_all_called=False)
async def test_address_history_pagination(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    ids = [f"{i:064x}" for i in range(1, 5)]
    addr = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"
    p1 = respx_mock.get(f"{A}/address/{addr}/txs").mock(
        return_value=httpx.Response(200, json=[fixture_tx(t) for t in ids[:3]]))
    respx_mock.get(f"{A}/address/{addr}/txs/chain/{ids[2]}").mock(
        return_value=httpx.Response(200, json=[fixture_tx(ids[3])]))
    respx_mock.get(f"{A}/address/{addr}/txs/chain/{ids[3]}").mock(return_value=httpx.Response(200, json=[]))
    got = [t.txid async for t in client.iter_address_txs(addr)]
    assert got == ids
    limited = [t.txid async for t in make_client().iter_address_txs(addr, max_txs=2)]
    assert limited == ids[:2] and p1.call_count >= 1


@pytest.mark.respx(assert_all_called=False)
async def test_address_txs_warm_the_tx_cache(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    addr = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"
    respx_mock.get(f"{A}/address/{addr}/txs").mock(return_value=httpx.Response(200, json=[fixture_tx()]))
    tx_route = respx_mock.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx()))
    await client.get_address_txs(addr)
    await client.get_tx(TXID)
    assert tx_route.call_count == 0


@pytest.mark.respx(assert_all_called=False)
async def test_price_uses_price_backend_and_hour_bucket(make_client, respx_mock):
    client = make_client()
    route = respx_mock.get(f"{A}/v1/historical-price", params={"currency": "USD", "timestamp": "1749186000"}).mock(
        return_value=httpx.Response(200, json={"prices": [{"time": 1749186000, "USD": 102863}]}))
    assert await client.get_price_usd(1749188499) == 102863.0
    assert await client.get_price_usd(1749188000) == 102863.0
    assert route.call_count == 1


@pytest.mark.respx(assert_all_called=False)
async def test_price_unavailable_returns_none(make_client, respx_mock):
    client = make_client()
    respx_mock.get(f"{A}/v1/historical-price").mock(return_value=httpx.Response(404))
    assert await client.get_price_usd(1749188499) is None


@pytest.mark.respx(assert_all_called=False)
async def test_get_address(make_client, respx_mock):
    client = make_client()
    body = json.loads((FIX / "address_genesis.json").read_text())
    respx_mock.get(f"{A}/address/1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa").mock(return_value=httpx.Response(200, json=body))
    st = await client.get_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
    assert st.address == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
