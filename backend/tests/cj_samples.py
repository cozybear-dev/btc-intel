"""Synthetic CoinJoin-shaped transactions mirroring real mainnet structures (see Task 10 rules)."""

from btcintel.chain.models import Tx
from tests.builders import mk_tx

W = "v0_p2wpkh"
TR = "v1_p2tr"


def _addr(i: int) -> str:
    return f"bc1-sample-{i}"


def whirlpool_mix() -> Tx:
    ins = [(_addr(i), v, W) for i, v in enumerate([1_000_000] * 3 + [1_006_050] * 2)]
    return mk_tx(ins, [(_addr(10 + i), 1_000_000, W) for i in range(5)], version=1)


def ashigaru_remix() -> Tx:
    ins = [(_addr(i), v, W) for i, v in enumerate([2_500_000] * 4 + [2_505_000] * 2)]
    return mk_tx(ins, [(_addr(20 + i), 2_500_000, W) for i in range(6)], version=1)


def whirlpool_tx0(n_inputs: int = 1) -> Tx:
    ins = [(_addr(30 + i), 720_000 // n_inputs, W) for i in range(n_inputs)]
    outs = [(_addr(40), 5_000, W), (_addr(41), 67_648, W)] + [(_addr(42 + i), 106_352, W) for i in range(5)]
    return mk_tx(ins, outs, version=1, op_returns=[bytes(range(64))])


def thorchain_swap() -> Tx:
    memo = b"=:ETH.ETH:0xe6a30f4f3bad978910e2cbb4d97581f5b5a0ade0"
    return mk_tx([(_addr(50), 500_000, W)], [(_addr(51), 120_000, W), (_addr(52), 370_000, W)],
                 op_returns=[memo])


def wasabi2_round(version: int = 1) -> Tx:
    ins = [(_addr(60 + i), 1_000_000, W if i % 2 else TR) for i in range(12)]
    values = [1_000_000] * 3 + [500_000] * 3 + [200_000] * 2 + [131_072] * 2 + [59_049, 100_000, 4_213_337]
    outs = [(_addr(80 + i), v, W if i % 2 else TR) for i, v in enumerate(values)]
    return mk_tx(ins, outs, version=version, locktime=0)


def wasabi1_round() -> Tx:
    ins = [(_addr(100 + i), 20_000_000, W) for i in range(60)]
    outs = [(_addr(200 + i), 10_987_000, W) for i in range(50)]
    outs += [(_addr(300 + i), 1_000_000 + i * 1_111, W) for i in range(30)]
    return mk_tx(ins, outs, version=1)


def joinmarket_round() -> Tx:
    ins = [(_addr(400 + i), 40_000_000, W) for i in range(11)]
    outs = [(_addr(420 + i), 35_281_835, W) for i in range(5)]
    outs += [(_addr(430 + i), v, W) for i, v in enumerate([12_345_678, 23_456_789, 34_567_890, 45_678_901])]
    return mk_tx(ins, outs, version=2, locktime=846_005, sequence=0xFFFFFFFE)


def stonewall() -> Tx:
    ins = [(_addr(500 + i), 400_000, W) for i in range(3)]
    return mk_tx(ins, [(_addr(510), 50_000, W), (_addr(511), 50_000, W),
                       (_addr(512), 123_456, W), (_addr(513), 654_321, W)])


def generic_equal() -> Tx:
    return mk_tx([(_addr(600), 50_000, W), (_addr(601), 40_000, W)],
                 [(_addr(610), 40_000, W), (_addr(611), 40_000, W), (_addr(612), 777, W)])
