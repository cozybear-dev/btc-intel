"""Source-agnostic chain data models (shaped after the Esplora REST API)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, computed_field


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class TxOut(_Frozen):
    n: int
    value: int
    script_type: str
    address: str | None = None
    script_hex: str = ""


class TxIn(_Frozen):
    n: int
    prev_txid: str
    prev_vout: int
    prevout: TxOut | None = None
    is_coinbase: bool = False
    sequence: int
    scriptsig_hex: str = ""
    scriptsig_asm: str = ""
    witness: list[str] = []
    inner_redeemscript_asm: str | None = None
    inner_witnessscript_asm: str | None = None

    @property
    def value(self) -> int:
        return self.prevout.value if self.prevout else 0

    @property
    def address(self) -> str | None:
        return self.prevout.address if self.prevout else None

    @property
    def script_type(self) -> str | None:
        return self.prevout.script_type if self.prevout else None


class TxStatus(_Frozen):
    confirmed: bool
    block_height: int | None = None
    block_hash: str | None = None
    block_time: int | None = None


class Tx(_Frozen):
    txid: str
    version: int
    locktime: int
    vin: list[TxIn]
    vout: list[TxOut]
    size: int
    weight: int
    fee: int
    status: TxStatus

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_coinbase(self) -> bool:
        return bool(self.vin) and self.vin[0].is_coinbase

    @computed_field  # type: ignore[prop-decorator]
    @property
    def input_value(self) -> int:
        return sum(i.value for i in self.vin)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def output_value(self) -> int:
        return sum(o.value for o in self.vout)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def vsize(self) -> int:
        return (self.weight + 3) // 4

    @computed_field  # type: ignore[prop-decorator]
    @property
    def feerate(self) -> float:
        return round(self.fee / self.vsize, 3) if self.vsize else 0.0

    def spendable_outputs(self) -> list[TxOut]:
        return [o for o in self.vout if o.script_type != "op_return"]

    def input_addresses(self) -> list[str]:
        return list(dict.fromkeys(i.address for i in self.vin if i.address))

    def output_addresses(self) -> list[str]:
        return list(dict.fromkeys(o.address for o in self.vout if o.address))


class Outspend(_Frozen):
    spent: bool
    txid: str | None = None
    vin: int | None = None
    status: TxStatus | None = None


class AddressStats(_Frozen):
    address: str
    tx_count: int
    funded_txo_count: int
    funded_sum: int
    spent_txo_count: int
    spent_sum: int
    mempool_tx_count: int = 0
    mempool_delta: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def balance(self) -> int:
        return self.funded_sum - self.spent_sum
