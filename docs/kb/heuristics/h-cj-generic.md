# H-CJ-GENERIC — Generic equal-output multi-input transaction

> **Family:** coinjoin · **Status in btc-intel:** planned · **Confidence:** low · **Parent:** [H-CJ](h-cj.md)

## Summary

A transaction with at least two inputs and at least two equal-value outputs is a weak CoinJoin indicator: it may be a manual or unknown CoinJoin, or just a batch payment.

## How it works

This is the fallback when no specific implementation matches. It exists so that CIOH is not applied blindly to transactions that may combine several owners [meiklejohn2013][crocsmuni-coinjoin].

## Signals and thresholds

- Largest equal-output group ≥ 2 and `n_in ≥ 2`. Confidence 0.3.

## False positives and limitations

- Batched payments with repeated amounts. One of 102 ordinary transactions sampled on 2026-09-25 matched.

## Evasion / countermeasures

—

## Detection in btc-intel

Planned — Plan 2 implements this in `backend/btcintel/heuristics/coinjoin.py`.

## Case examples

No public case study is attached to this technique yet.

## References

- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
- [crocsmuni-coinjoin] CRoCS MUNI (2026). *coinjoin-analysis: processing and analysis of Wasabi 1.x/2.x, Whirlpool and JoinMarket coinjoins (with Dumplings datasets)*. <https://github.com/crocs-muni/coinjoin-analysis>
