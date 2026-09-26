# H-CJ-WASABI2 — WabiSabi (Wasabi 2.x and forks)

> **Family:** coinjoin · **Status in btc-intel:** implemented · **Confidence:** high · **Parent:** [H-CJ](h-cj.md)

## Summary

WabiSabi rounds run by Wasabi 2.x, Ginger and community coordinators mix many inputs into outputs drawn from a fixed set of standard denominations.

## How it works

```
 20–300 segwit inputs (P2WPKH / P2TR)
 ─────────────► one round ─────────────►  outputs mostly in standard denominations
                                          (several equal-value groups, a few change outputs)
```
The crocs-muni data lists the coordinators behind these rounds (for example zkSNACKs from June 2022, kruw.io from May 2024, Ginger from June 2024 and an open coordinator from May 2025) [crocsmuni-coinjoin]. Rounds sampled from those lists on 2026-09-25 all used nVersion 1 and nLockTime 0, and 94–98% of their outputs were standard denominations.

## Signals and thresholds

- At least 5 inputs; every input and output is P2WPKH or P2TR.
- nVersion 1 and nLockTime 0.
- At least 75% of outputs are standard denominations: 2ⁿ, 3ⁿ, 2·3ⁿ, 10ⁿ, 2·10ⁿ and 5·10ⁿ sats, at or above 5,000 sats.
- At least one equal-value group.

## False positives and limitations

- Large batched payments that happen to use round denominations with nVersion 1 would match; none were seen in the ordinary-transaction sample.

## Evasion / countermeasures

None at the transaction level: the structure is the point of a CoinJoin. Evasion happens after the mix ([H-CJ-POST](h-cj-post.md)).

## Detection in btc-intel

Implemented in `backend/btcintel/heuristics/coinjoin.py` (`classify_coinjoin`).

## Case examples

The PoPETs 2026 ecosystem study analyses Wasabi 1.x, Wasabi 2.x and Whirlpool coordinators [popets2026coinjoin].

## References

- [popets2026coinjoin] — (2026). *CoinJoin ecosystem insights for Wasabi 1.x, Wasabi 2.x and Whirlpool coordinator-based privacy mixers*. PoPETs 2026. <https://petsymposium.org/popets/2026/popets-2026-0061.php>
- [crocsmuni-coinjoin] CRoCS MUNI (2026). *coinjoin-analysis: processing and analysis of Wasabi 1.x/2.x, Whirlpool and JoinMarket coinjoins (with Dumplings datasets)*. <https://github.com/crocs-muni/coinjoin-analysis>
