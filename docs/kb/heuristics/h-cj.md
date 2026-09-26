# H-CJ — CoinJoin detection

> **Family:** coinjoin · **Status in btc-intel:** planned · **Confidence:** high

## Summary

A CoinJoin combines inputs from many users into one transaction with equal-value outputs, so an observer cannot tell which input paid which output. Detecting CoinJoins matters twice: it stops [H-CIOH](h-cioh.md) from merging unrelated users, and it marks where funds were deliberately obfuscated [meiklejohn2013][popets2026coinjoin].

## How it works

btc-intel classifies transactions by the structure of each CoinJoin implementation, testing the strongest signatures first:

| Order | Kind | Page | Multi-party |
|---|---|---|---|
| 1 | Whirlpool mix | [H-CJ-WHIRLPOOL](h-cj-whirlpool.md) | yes |
| 2 | Whirlpool Tx0 | [H-CJ-WHIRLPOOL-TX0](h-cj-whirlpool-tx0.md) | no (single owner) |
| 3 | WabiSabi (Wasabi 2.x) | [H-CJ-WASABI2](h-cj-wasabi2.md) | yes |
| 4 | ZeroLink (Wasabi 1.x) | [H-CJ-WASABI1](h-cj-wasabi1.md) | yes |
| 5 | JoinMarket | [H-CJ-JOINMARKET](h-cj-joinmarket.md) | yes |
| 6 | Stonewall | [H-CJ-STONEWALL](h-cj-stonewall.md) | yes |
| 7 | Generic equal-output | [H-CJ-GENERIC](h-cj-generic.md) | yes |

The thresholds were calibrated against the crocs-muni coinjoin-analysis ground truth (coordinator transaction lists and Dumplings scanner output) [crocsmuni-coinjoin]. On 2026-09-25, 57 of 60 randomly sampled WabiSabi rounds were classified as WabiSabi, and the other 3 were still flagged as generic CoinJoins. Every sampled Whirlpool mix, Tx0 and Wasabi 1 round was classified correctly, and none of 102 ordinary mainnet transactions was flagged as a strong CoinJoin kind.

## Signals and thresholds

- Equal-value output groups, input and output counts, script types, nVersion/nLockTime, OP_RETURN payloads and pool denominations. See each child page.

## False positives and limitations

- Batched exchange payouts with repeated amounts can look like generic or JoinMarket-style CoinJoins; these kinds therefore carry low confidence.

## Evasion / countermeasures

Mixing structures that avoid equal outputs (PayJoin, Stonewall) and custodial mixers that leave no CoinJoin on chain ([O-CUSTODIAL-MIXER](../techniques/o-custodial-mixer.md)).

## Detection in btc-intel

The `H-CJ` detector emits `coinjoin:<kind>` with the denomination, anonymity set and equal-group count. [H-CIOH](h-cioh.md) and [H-CHG](h-chg.md) are suppressed for multi-party kinds, and tracing stops at CoinJoins unless told to continue.

Planned — Plan 2 implements this in `backend/btcintel/heuristics/coinjoin.py`.

## Case examples

No public case study is attached to this technique yet.

## References

- [popets2026coinjoin] — (2026). *CoinJoin ecosystem insights for Wasabi 1.x, Wasabi 2.x and Whirlpool coordinator-based privacy mixers*. PoPETs 2026. <https://petsymposium.org/popets/2026/popets-2026-0061.php>
- [crocsmuni-coinjoin] CRoCS MUNI (2026). *coinjoin-analysis: processing and analysis of Wasabi 1.x/2.x, Whirlpool and JoinMarket coinjoins (with Dumplings datasets)*. <https://github.com/crocs-muni/coinjoin-analysis>
- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
