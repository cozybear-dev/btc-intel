import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from btcintel.trace.taint import (
    backward,
    fifo_backward,
    fifo_forward,
    forward,
    haircut_backward,
    haircut_forward,
    poison_forward,
)
from tests.builders import mk_tx

INS, OUTS = [60_000, 40_000], [70_000, 29_000]


def test_worked_example():
    assert haircut_forward(INS, OUTS, {1: 40_000}) == pytest.approx({0: 28_000, 1: 11_600})
    assert fifo_forward(INS, OUTS, {1: 40_000}) == {0: 10_000, 1: 29_000}
    assert poison_forward(INS, OUTS, {1: 40_000}) == {0: 70_000, 1: 29_000}
    assert haircut_backward(INS, OUTS, {0: 70_000}) == pytest.approx({0: 42_000, 1: 28_000})
    assert fifo_backward(INS, OUTS, {1: 29_000}) == {1: 29_000}


def test_clamping_and_empty():
    assert haircut_forward(INS, OUTS, {0: -5, 7: 100}) == {}
    assert fifo_forward(INS, OUTS, {0: 10**12}) == {0: 60_000}
    assert poison_forward(INS, OUTS, {}) == {}


def test_tx_level_api_and_unknown_model():
    tx = mk_tx([("a", 60_000), ("b", 40_000)], [("c", 70_000), ("d", 29_000)])
    assert forward("fifo", tx, {1: 40_000}) == {0: 10_000, 1: 29_000}
    assert backward("haircut", tx, {0: 70_000}) == pytest.approx({0: 42_000, 1: 28_000})
    with pytest.raises(ValueError, match="unknown taint model"):
        forward("magic", tx, {})


@st.composite
def tx_values(draw):
    ins = draw(st.lists(st.integers(1, 10**8), min_size=1, max_size=6))
    fee = draw(st.integers(0, min(ins)))
    total = sum(ins) - fee
    k = draw(st.integers(1, 6))
    cuts = sorted(draw(st.lists(st.integers(0, total), min_size=k - 1, max_size=k - 1)))
    outs = [b - a for a, b in zip([0, *cuts], [*cuts, total], strict=True)]
    return ins, outs


def _taint(data, values):
    return {i: data.draw(st.integers(0, v)) for i, v in enumerate(values) if data.draw(st.booleans())}


@given(tx_values(), st.data())
@settings(max_examples=300, deadline=None)
def test_forward_models_conserve_and_bound(tv, data):
    ins, outs = tv
    taint = _taint(data, ins)
    for fn in (haircut_forward, fifo_forward):
        res = fn(ins, outs, taint)
        assert sum(res.values()) <= sum(taint.values()) + 1e-6
        assert all(res[j] <= outs[j] + 1e-6 for j in res)


@given(tx_values(), st.data())
@settings(max_examples=300, deadline=None)
def test_backward_models_conserve_and_bound(tv, data):
    ins, outs = tv
    taint = _taint(data, outs)
    for fn in (haircut_backward, fifo_backward):
        res = fn(ins, outs, taint)
        assert sum(res.values()) <= sum(taint.values()) + 1e-6
        assert all(res[i] <= ins[i] + 1e-6 for i in res)


@given(tx_values(), st.data())
@settings(max_examples=200, deadline=None)
def test_haircut_and_fifo_are_linear_in_inputs(tv, data):
    ins, outs = tv
    taint = _taint(data, ins)
    items = list(taint.items())
    a, b = dict(items[: len(items) // 2]), dict(items[len(items) // 2 :])
    for fn in (haircut_forward, fifo_forward):
        whole, pa, pb = fn(ins, outs, taint), fn(ins, outs, a), fn(ins, outs, b)
        for j in set(whole) | set(pa) | set(pb):
            assert whole.get(j, 0) == pytest.approx(pa.get(j, 0) + pb.get(j, 0), abs=1e-6)
