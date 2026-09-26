"""H-TAINT: how much of each output derives from tainted inputs (and vice versa), per transaction."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from btcintel.chain.models import Tx

TaintMap = dict[int, float]
TAINT_MODELS = ("poison", "haircut", "fifo")
Model = Callable[[Sequence[int], Sequence[int], Mapping[int, float]], TaintMap]


def _clamp(values: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    return {i: min(float(t), float(values[i])) for i, t in taint.items()
            if 0 <= i < len(values) and t > 0 and values[i] > 0}


def _starts(values: Sequence[int]) -> list[int]:
    out, acc = [], 0
    for v in values:
        out.append(acc)
        acc += v
    return out


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _map_ranges(src: Sequence[int], dst: Sequence[int], taint: TaintMap) -> TaintMap:
    """Tainted sats are the first `t` sats of each source slot; map them onto destination slots."""
    src_starts, dst_starts = _starts(src), _starts(dst)
    res: TaintMap = {}
    for i, amount in taint.items():
        a0, a1 = src_starts[i], src_starts[i] + amount
        for j, w in enumerate(dst):
            ov = _overlap(a0, a1, dst_starts[j], dst_starts[j] + w)
            if ov > 0:
                res[j] = res.get(j, 0.0) + ov
    return res


def poison_forward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    return {j: float(v) for j, v in enumerate(outs) if v > 0} if _clamp(ins, taint) else {}


def haircut_forward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    t, total = _clamp(ins, taint), sum(ins)
    if not t or total <= 0:
        return {}
    fraction = sum(t.values()) / total
    return {j: v * fraction for j, v in enumerate(outs) if v > 0}


def fifo_forward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    return _map_ranges(ins, outs, _clamp(ins, taint))


def poison_backward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    return {i: float(v) for i, v in enumerate(ins) if v > 0} if _clamp(outs, taint) else {}


def haircut_backward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    t, total = _clamp(outs, taint), sum(ins)
    if not t or total <= 0:
        return {}
    amount = sum(t.values())
    return {i: amount * v / total for i, v in enumerate(ins) if v > 0}


def fifo_backward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    return _map_ranges(outs, ins, _clamp(outs, taint))


_FORWARD: dict[str, Model] = {"poison": poison_forward, "haircut": haircut_forward, "fifo": fifo_forward}
_BACKWARD: dict[str, Model] = {"poison": poison_backward, "haircut": haircut_backward, "fifo": fifo_backward}


def forward(model: str, tx: Tx, tainted_inputs: Mapping[int, float]) -> TaintMap:
    if model not in _FORWARD:
        raise ValueError(f"unknown taint model {model!r}")
    return _FORWARD[model]([i.value for i in tx.vin], [o.value for o in tx.vout], tainted_inputs)


def backward(model: str, tx: Tx, tainted_outputs: Mapping[int, float]) -> TaintMap:
    if model not in _BACKWARD:
        raise ValueError(f"unknown taint model {model!r}")
    return _BACKWARD[model]([i.value for i in tx.vin], [o.value for o in tx.vout], tainted_outputs)
