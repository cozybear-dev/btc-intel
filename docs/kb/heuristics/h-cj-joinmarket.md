# H-CJ-JOINMARKET — JoinMarket

> **Family:** coinjoin · **Status in btc-intel:** planned · **Confidence:** medium · **Parent:** [H-CJ](h-cj.md)

## Summary

JoinMarket is a peer-to-peer CoinJoin market: a taker pays makers to join a transaction, which yields n equal outputs plus up to one change output per participant, with no coordinator fee output.

## How it works

```
 taker + makers inputs ─► n equal outputs  +  ≤ n change outputs
```
A JoinMarket-style round from the Dumplings data had 11 inputs and 9 outputs (5 equal), nVersion 2, an anti-fee-sniping nLockTime and nSequence 0xfffffffe [crocsmuni-coinjoin]. The original JoinMarket repository was archived on 27 April 2026; joinmarket-ng and the Jam web UI continue [atlas21-coinjoin-2026].

## Signals and thresholds

- Largest equal group n ≥ 3; `n_in ≥ n`; `n_out ≤ 2n + 1`; no OP_RETURN.

## False positives and limitations

- Batched payouts that contain three or more identical amounts; confidence is therefore 0.6.

## Evasion / countermeasures

Makers' fidelity bonds and randomised amounts limit analysis; post-mix behaviour matters ([H-CJ-POST](h-cj-post.md)).

## Detection in btc-intel

Planned — Plan 2 implements this in `backend/btcintel/heuristics/coinjoin.py`.

## Case examples

No public case study is attached to this technique yet.

## References

- [crocsmuni-coinjoin] CRoCS MUNI (2026). *coinjoin-analysis: processing and analysis of Wasabi 1.x/2.x, Whirlpool and JoinMarket coinjoins (with Dumplings datasets)*. <https://github.com/crocs-muni/coinjoin-analysis>
- [atlas21-coinjoin-2026] — (2026). *CoinJoin in 2026: Wasabi, JoinMarket and Ashigaru compared*. <https://atlas21.com/coinjoin-comparison-of-tools-to-improve-privacy-on-bitcoin/>
