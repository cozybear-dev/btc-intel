"""Incrementally built address↔transaction graph with streaming events."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from btcintel.chain.models import Tx
from btcintel.heuristics.flags import tx_flags
from btcintel.labels.lookup import LabelLookup

StopReason = Literal["unspent", "labeled", "coinjoin", "max_hops", "min_value", "max_txs", "coinbase", "peel_off"]
Emit = Callable[[dict[str, Any]], None]


class GraphNode(BaseModel):
    id: str
    kind: Literal["tx", "address", "script"]
    label: str
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    value: int
    taint: float = 0.0


class Stop(BaseModel):
    node: str
    reason: StopReason
    taint: float = 0.0
    detail: str = ""


def tx_node_id(txid: str) -> str:
    return f"tx:{txid}"


def addr_node_id(address: str) -> str:
    return f"addr:{address}"


class GraphBuilder:
    def __init__(self, labels: LabelLookup, emit: Emit | None = None) -> None:
        self.labels = labels
        self.emit = emit
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}
        self.stops: list[Stop] = []
        self.txs: dict[str, Tx] = {}
        self.truncated = False

    def _send(self, kind: str, items: list[BaseModel]) -> None:
        if self.emit and items:
            self.emit({"type": kind, "items": [i.model_dump() for i in items]})

    def _address_node(self, address: str) -> GraphNode | None:
        nid = addr_node_id(address)
        if nid in self.nodes:
            return None
        info = self.labels.lookup(address)
        node = GraphNode(id=nid, kind="address", label=info.label or f"{address[:8]}…{address[-4:]}",
                         data=info.to_dict())
        self.nodes[nid] = node
        return node

    def add_tx(self, tx: Tx) -> bool:
        if tx.txid in self.txs:
            return False
        self.txs[tx.txid] = tx
        node = GraphNode(id=tx_node_id(tx.txid), kind="tx", label=tx.txid[:8], data={
            "txid": tx.txid, "block_height": tx.status.block_height, "block_time": tx.status.block_time,
            "confirmed": tx.status.confirmed, "fee": tx.fee, "n_in": len(tx.vin), "n_out": len(tx.vout),
            "value": tx.output_value, "flags": tx_flags(tx),
        })
        self.nodes[node.id] = node
        new_nodes: list[BaseModel] = [node]
        new_edges: list[BaseModel] = []
        for txin in tx.vin:
            if txin.address is None:
                continue
            an = self._address_node(txin.address)
            if an:
                new_nodes.append(an)
            edge = GraphEdge(id=f"in:{tx.txid}:{txin.n}", source=addr_node_id(txin.address),
                             target=node.id, value=txin.value)
            self.edges[edge.id] = edge
            new_edges.append(edge)
        self._send("nodes", new_nodes)
        self._send("edges", new_edges)
        return True

    def add_output(self, tx: Tx, n: int, taint: float = 0.0) -> str:
        out = tx.vout[n]
        target = addr_node_id(out.address) if out.address else f"script:{tx.txid}:{n}"
        new_nodes: list[BaseModel] = []
        if out.address:
            an = self._address_node(out.address)
            if an:
                new_nodes.append(an)
        elif target not in self.nodes:
            node = GraphNode(id=target, kind="script", label=out.script_type.upper(),
                             data={"script_type": out.script_type, "value": out.value})
            self.nodes[target] = node
            new_nodes.append(node)
        eid = f"out:{tx.txid}:{n}"
        prev = self.edges.get(eid)
        edge = GraphEdge(id=eid, source=tx_node_id(tx.txid), target=target, value=out.value,
                         taint=(prev.taint if prev else 0.0) + taint)
        self.edges[eid] = edge
        self._send("nodes", new_nodes)
        self._send("edges", [edge])
        return target

    def add_input_taint(self, tx: Tx, vin: int, taint: float) -> None:
        eid = f"in:{tx.txid}:{vin}"
        edge = self.edges.get(eid)
        if edge is None:
            return
        self.edges[eid] = edge.model_copy(update={"taint": edge.taint + taint})
        self._send("edges", [self.edges[eid]])

    def stop(self, node: str, reason: StopReason, taint: float = 0.0, detail: str = "") -> None:
        stop = Stop(node=node, reason=reason, taint=round(taint, 2), detail=detail)
        self.stops.append(stop)
        if self.emit:
            self.emit({"type": "stop", "item": stop.model_dump()})
