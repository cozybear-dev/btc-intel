# H-CJ-WASABI1 — ZeroLink (Wasabi 1.x)

> **Family:** coinjoin · **Status in btc-intel:** planned · **Confidence:** high · **Parent:** [H-CJ](h-cj.md)

## Summary

Wasabi 1.x (ZeroLink) rounds, 2018–2024, produced one large group of equal outputs of about 0.1 BTC plus change outputs.

## How it works

```
 ~50–100 P2WPKH inputs ──► round ──► ~50+ outputs of ≈0.1 BTC (anonymity set)
                                     + coordinator fee + change outputs
```
Wasabi 1 rounds sampled from the Dumplings data had equal outputs of about 10,987,000 sats, with anonymity sets of 46–65, only P2WPKH scripts and nVersion 1 [crocsmuni-coinjoin].

## Signals and thresholds

- The largest equal-output group has ≥10 outputs, valued 7,000,000–13,000,000 sats.
- All inputs and outputs are P2WPKH.

## False positives and limitations

- Other ZeroLink-style coordinators produce the same shape and are classified as Wasabi 1.

## Evasion / countermeasures

Post-mix behaviour determines privacy ([H-CJ-POST](h-cj-post.md)).

## Detection in btc-intel

Planned — Plan 2 implements this in `backend/btcintel/heuristics/coinjoin.py`.

## Case examples

See [popets2026coinjoin] for ecosystem-level statistics.

## References

- [popets2026coinjoin] — (2026). *CoinJoin ecosystem insights for Wasabi 1.x, Wasabi 2.x and Whirlpool coordinator-based privacy mixers*. PoPETs 2026. <https://petsymposium.org/popets/2026/popets-2026-0061.php>
- [crocsmuni-coinjoin] CRoCS MUNI (2026). *coinjoin-analysis: processing and analysis of Wasabi 1.x/2.x, Whirlpool and JoinMarket coinjoins (with Dumplings datasets)*. <https://github.com/crocs-muni/coinjoin-analysis>
