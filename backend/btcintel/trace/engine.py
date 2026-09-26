"""Follow-the-money tracing: expand the highest tainted value first, forward or backward."""

from __future__ import annotations

import heapq
import itertools
from contextlib import aclosing
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from btcintel.chain.budget import BudgetExceeded, CallBudget, budget_scope
from btcintel.chain.errors import SourceError
from btcintel.chain.models import Tx
from btcintel.chain.source import ChainSource
from btcintel.chain.validate import is_address, is_txid, normalize_address
from btcintel.heuristics.change import remainder_output
from btcintel.heuristics.coinjoin import MULTIPARTY_KINDS, classify_coinjoin
from btcintel.labels.lookup import LabelLookup
from btcintel.trace import taint as taint_models
from btcintel.trace.graph import (
    Emit,
    GraphBuilder,
    GraphEdge,
    GraphNode,
    Stop,
    addr_node_id,
    tx_node_id,
)


class TracePolicy(BaseModel):
    direction: Literal["forward", "backward"] = "forward"
    max_hops: int = Field(6, ge=1, le=50)
    max_txs: int = Field(200, ge=1, le=5000)
    max_calls: int = Field(600, ge=1, le=50_000)
    min_value_sats: int = Field(10_000, ge=0)
    taint_model: Literal["poison", "haircut", "fifo"] = "haircut"
    stop_categories: list[str] | None = None
    coinjoin: Literal["stop", "through"] = "stop"
    peel_mode: bool = False
    max_address_txs: int = Field(50, ge=1, le=1000)


class TraceSeed(BaseModel):
    txid: str | None = None
    vout: int | None = Field(None, ge=0)
    address: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> TraceSeed:
        if (self.txid is None) == (self.address is None):
            raise ValueError("give exactly one of txid or address")
        if self.txid is not None:
            if not is_txid(self.txid):
                raise ValueError("invalid txid")
            self.txid = self.txid.lower()
        else:
            if not is_address(self.address or ""):
                raise ValueError("invalid address")
            if self.vout is not None:
                raise ValueError("vout only applies to a txid seed")
            self.address = normalize_address(self.address or "")
        return self


class TraceResult(BaseModel):
    seed: TraceSeed
    policy: TracePolicy
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stops: list[Stop]
    incomplete: bool
    reason: str | None = None
    calls_used: int
    txs_expanded: int


async def trace(seed: TraceSeed, policy: TracePolicy, *, chain: ChainSource, labels: LabelLookup,
                emit: Emit | None = None) -> TraceResult:
    graph = GraphBuilder(labels, emit)
    budget = CallBudget(policy.max_calls)
    incomplete, reason = False, None
    with budget_scope(budget):
        try:
            if policy.direction == "forward":
                await _forward(seed, policy, chain, labels, graph)
            else:
                await _backward(seed, policy, chain, labels, graph)
        except BudgetExceeded as e:
            incomplete, reason = True, str(e)
        except SourceError as e:
            incomplete, reason = True, f"chain source failed: {e}"
    if graph.truncated and not incomplete:
        incomplete, reason = True, f"stopped after {policy.max_txs} transactions (max_txs)"
    if emit:
        emit({"type": "done", "incomplete": incomplete, "reason": reason, "calls_used": budget.used})
    return TraceResult(seed=seed, policy=policy, nodes=list(graph.nodes.values()),
                       edges=list(graph.edges.values()), stops=graph.stops, incomplete=incomplete,
                       reason=reason, calls_used=budget.used, txs_expanded=len(graph.txs))


def _is_stopping_coinjoin(tx: Tx, policy: TracePolicy) -> str | None:
    if policy.coinjoin != "stop":
        return None
    m = classify_coinjoin(tx)
    return m.kind if m is not None and m.kind in MULTIPARTY_KINDS else None


async def _forward(seed: TraceSeed, policy: TracePolicy, chain: ChainSource, labels: LabelLookup,
                   g: GraphBuilder) -> None:
    heap: list[tuple[float, int, int, str, int]] = []
    counter = itertools.count()
    poisoned: set[str] = set()
    # Outputs paying an address seed start at full value; taint reaching them again (e.g. the
    # address's own change) is already counted and must not be followed twice.
    seeded: set[tuple[str, int]] = set()

    def follow(tx: Tx, n: int, amount: float, hop: int) -> None:
        target = g.add_output(tx, n, amount)
        out = tx.vout[n]
        if out.address is None:
            return
        info = labels.lookup(out.address)
        if info.stop_category:
            g.stop(target, "labeled", amount, f"{info.stop_category}: {info.label}")
            return
        heapq.heappush(heap, (-amount, hop, next(counter), tx.txid, n))

    if seed.txid is not None:
        tx = await chain.get_tx(seed.txid)
        g.add_tx(tx)
        if seed.vout is not None and seed.vout >= len(tx.vout):
            raise ValueError(f"transaction has no output {seed.vout}")
        outs = [seed.vout] if seed.vout is not None else [o.n for o in tx.spendable_outputs()]
        for n in outs:
            follow(tx, n, float(tx.vout[n].value), 1)
    else:
        async with aclosing(chain.iter_address_txs(seed.address or "", policy.max_address_txs)) as txs:
            async for tx in txs:
                for out in tx.vout:
                    if out.address == seed.address:
                        g.add_tx(tx)
                        seeded.add((tx.txid, out.n))
                        follow(tx, out.n, float(out.value), 1)

    while heap:
        neg, hop, _, txid, vout = heapq.heappop(heap)
        amount = -neg
        node = addr_node_id(g.txs[txid].vout[vout].address or "")
        if amount < policy.min_value_sats:
            g.stop(node, "min_value", amount)
            continue
        if hop > policy.max_hops:
            g.stop(node, "max_hops", amount)
            continue
        spends = await chain.get_outspends(txid)
        sp = spends[vout] if vout < len(spends) else None
        if sp is None or not sp.spent or sp.txid is None or sp.vin is None:
            g.stop(node, "unspent", amount)
            continue
        if sp.txid not in g.txs and len(g.txs) >= policy.max_txs:
            g.truncated = True
            g.stop(node, "max_txs", amount)
            continue
        child = await chain.get_tx(sp.txid)
        g.add_tx(child)
        g.add_input_taint(child, sp.vin, amount)
        cj_kind = _is_stopping_coinjoin(child, policy)
        if cj_kind:
            g.stop(tx_node_id(child.txid), "coinjoin", amount, cj_kind)
            continue
        if policy.taint_model == "poison":
            if child.txid in poisoned:
                continue
            poisoned.add(child.txid)
        delta = taint_models.forward(policy.taint_model, child, {sp.vin: amount})
        targets = [(n, t) for n, t in sorted(delta.items()) if (child.txid, n) not in seeded]
        if policy.peel_mode:
            keep = remainder_output(child)
            for n, t in targets:
                if n != keep and t > 0:
                    g.stop(g.add_output(child, n, t), "peel_off", t)
            targets = [(n, t) for n, t in targets if n == keep]
        for n, t in targets:
            if t > 0:
                follow(child, n, t, hop + 1)


async def _backward(seed: TraceSeed, policy: TracePolicy, chain: ChainSource, labels: LabelLookup,
                    g: GraphBuilder) -> None:
    heap: list[tuple[float, int, int, str, int]] = []
    counter = itertools.count()
    # Outputs paying an address seed are traced from their own seed; an input spending one (the
    # address funding its own change) would trace the same funding twice.
    seeded: set[tuple[str, int]] = set()

    def push(amount: float, hop: int, txid: str, vin: int) -> None:
        heapq.heappush(heap, (-amount, hop, next(counter), txid, vin))

    def seed_outputs(tx: Tx, tainted: dict[int, float]) -> None:
        g.add_tx(tx)
        for n, t in tainted.items():
            g.add_output(tx, n, t)
        if tx.is_coinbase:
            g.stop(tx_node_id(tx.txid), "coinbase", sum(tainted.values()), "newly mined coins")
            return
        for i, t in sorted(taint_models.backward(policy.taint_model, tx, tainted).items()):
            if t > 0:
                push(t, 1, tx.txid, i)

    if seed.txid is not None:
        tx = await chain.get_tx(seed.txid)
        if seed.vout is not None:
            if seed.vout >= len(tx.vout):
                raise ValueError(f"transaction has no output {seed.vout}")
            seed_outputs(tx, {seed.vout: float(tx.vout[seed.vout].value)})
        elif tx.is_coinbase:
            seed_outputs(tx, {o.n: float(o.value) for o in tx.spendable_outputs()})
        else:
            g.add_tx(tx)
            for txin in tx.vin:
                push(float(txin.value), 1, tx.txid, txin.n)
    else:
        async with aclosing(chain.iter_address_txs(seed.address or "", policy.max_address_txs)) as txs:
            async for tx in txs:
                received = {o.n: float(o.value) for o in tx.vout if o.address == seed.address}
                if received:
                    seeded.update((tx.txid, n) for n in received)
                    seed_outputs(tx, received)

    while heap:
        neg, hop, _, txid, vin = heapq.heappop(heap)
        amount = -neg
        txin = g.txs[txid].vin[vin]
        if (txin.prev_txid, txin.prev_vout) in seeded:
            continue
        node = addr_node_id(txin.address) if txin.address else tx_node_id(txid)
        if amount < policy.min_value_sats:
            g.stop(node, "min_value", amount)
            continue
        if hop > policy.max_hops:
            g.stop(node, "max_hops", amount)
            continue
        if txin.address:
            info = labels.lookup(txin.address)
            if info.stop_category:
                g.stop(node, "labeled", amount, f"{info.stop_category}: {info.label}")
                continue
        if txin.prev_txid not in g.txs and len(g.txs) >= policy.max_txs:
            g.truncated = True
            g.stop(node, "max_txs", amount)
            continue
        parent = await chain.get_tx(txin.prev_txid)
        g.add_tx(parent)
        g.add_output(parent, txin.prev_vout, amount)
        if parent.is_coinbase:
            g.stop(tx_node_id(parent.txid), "coinbase", amount, "newly mined coins")
            continue
        cj_kind = _is_stopping_coinjoin(parent, policy)
        if cj_kind:
            g.stop(tx_node_id(parent.txid), "coinjoin", amount, cj_kind)
            continue
        for i, t in sorted(taint_models.backward(policy.taint_model, parent, {txin.prev_vout: amount}).items()):
            if t > 0:
                push(t, hop + 1, parent.txid, i)
