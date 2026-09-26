import pytest

from btcintel.chain.ratelimit import TokenBucket
from tests.fakes import FakeTime


async def test_burst_then_rate_limited():
    ft = FakeTime()
    bucket = TokenBucket(rate=1.0, burst=2, clock=ft.clock, sleep=ft.sleep)
    for _ in range(3):
        await bucket.acquire()
    assert ft.sleeps == [1.0]


async def test_penalize_blocks_until_deadline():
    ft = FakeTime()
    bucket = TokenBucket(rate=10.0, burst=1, clock=ft.clock, sleep=ft.sleep)
    await bucket.acquire()
    bucket.penalize(5.0)
    await bucket.acquire()
    assert ft.now == pytest.approx(5.0)


async def test_next_available_reports_wait():
    ft = FakeTime()
    bucket = TokenBucket(rate=2.0, burst=1, clock=ft.clock, sleep=ft.sleep)
    assert bucket.next_available() == 0.0
    await bucket.acquire()
    assert bucket.next_available() == pytest.approx(0.5)
    bucket.penalize(3.0)
    assert bucket.next_available() == pytest.approx(3.0)


@pytest.mark.parametrize("rate,burst", [(0, 1), (-1, 1), (1, 0)])
def test_invalid_parameters(rate, burst):
    with pytest.raises(ValueError):
        TokenBucket(rate=rate, burst=burst)
