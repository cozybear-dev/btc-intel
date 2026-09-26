# H-CJ-GENERIC — Generic equal-output multi-input transaction

> **Family:** coinjoin · **Status in btc-intel:** implemented · **Confidence:** low · **Parent:** [H-CJ](h-cj.md)

## Summary

A transaction with at least two inputs and at least two equal-value outputs is a weak CoinJoin indicator: it may be a manual or unknown CoinJoin, or just a batch payment.

## How it works

This is the fallback when no specific implementation matches. It exists so that CIOH is not applied blindly to transactions that may combine several owners [meiklejohn2013][crocsmuni-coinjoin].

## Signals and thresholds

- Largest equal-output group ≥ 2 and `n_in ≥ 2`. Confidence 0.3.
- Output structure: `n_out ≤ 2 × (outputs in equal groups) + 1`, because each participant receives at most one equal output and one change output, plus an optional fee output (Dumplings requires exactly as many change outputs as equal outputs).
- Single-actor guard (as in Dumplings' other-CoinJoin rule): the number of distinct input addresses must be at least the number of equal outputs, otherwise the transaction is one actor's batch, not several participants.

## False positives and limitations

- Batched payments with repeated amounts. One of 102 ordinary transactions sampled on 2026-09-25 matched.
- Before the single-actor guard, exchange batch payouts were flagged too: the Bitfinex backward trace (see [I-2016-BITFINEX](../incidents/i-2016-bitfinex.md)) stopped at June 2016 payouts such as `9ffe06de…a13d` (13 inputs from one address, four 20,000-sat outputs) and `147eca6c…f5` (18 inputs from three addresses, thirteen 20,000-sat outputs), and at payouts from up to 15 input addresses such as `7ed5eaa4…5e33` (seven 20,000-sat outputs among 48). All four are regression fixtures (`tests/fixtures/real/batch_payout`).

## Evasion / countermeasures

—

## Detection in btc-intel

Implemented in `backend/btcintel/heuristics/coinjoin.py` (`classify_coinjoin`).

## Case examples

No public case study is attached to this technique yet.

## References

- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
- [crocsmuni-coinjoin] CRoCS MUNI (2026). *coinjoin-analysis: processing and analysis of Wasabi 1.x/2.x, Whirlpool and JoinMarket coinjoins (with Dumplings datasets)*. <https://github.com/crocs-muni/coinjoin-analysis>
