# H-PEEL — Peel chain

> **Family:** pattern · **Status in btc-intel:** implemented · **Confidence:** medium

## Summary

A peel chain moves a large balance through a long sequence of transactions, each peeling a small payment off and forwarding the remainder to a fresh address. Following the remainder reconstructs the chain; the peels are payments or deposits.

## How it works

The Bitcoin Wiki: "a single address begins with a relatively large amount of bitcoins. A smaller amount is then peeled off this larger amount ... This process is repeated—potentially for hundreds or thousands of hops" [bitcoinwiki-privacy]. Meiklejohn et al. followed peeling chains to trace thefts to exchanges, and observed that the same pattern appears in withdrawals from exchanges and in mining-pool payouts [meiklejohn2013]. Kappos et al. designed a heuristic for peel chains and used it to validate and expand clusters [kappos2022].

```
 10.00 ─► 0.50 (peel)      9.49 ─► 0.40 (peel)      9.08 ─► ...
          9.49 (remainder)          9.08 (remainder)
```

## Signals and thresholds

- 1–2 inputs and exactly 2 spendable outputs, one of which carries ≥75% of the output value.
- The large output is itself spent by another peel-shaped transaction.

## False positives and limitations

- An ordinary payment with change looks like a single peel step; only a chain of steps is meaningful.

## Evasion / countermeasures

Splitting into many chains, varying the peel ratio, or inserting CoinJoins.

## Detection in btc-intel

`peel_step` findings on individual transactions; trace peel mode follows only the remainder (change, or else the largest output); `follow_peel_chain` and `POST /api/peel` walk a whole chain.

Shape test (`peel_shape`): not coinbase, 1–2 inputs, exactly 2 spendable outputs, and the larger output holds ≥75% of the output value. Evidence: `remainder_output`, `peel_output`, `peel_value`, `remainder_share`; confidence 0.5.

Implemented in `backend/btcintel/heuristics/patterns.py` (`peel_heuristic`).

## Case examples

Meiklejohn et al.'s theft tracing [meiklejohn2013]; see also [I-2016-BITFINEX](../incidents/i-2016-bitfinex.md).

## References

- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
- [kappos2022] George Kappos, Haaroon Yousaf, Rainer Stütz, Sofia Rollet, Bernhard Haslhofer, Sarah Meiklejohn (2022). *How to Peel a Million: Validating and Expanding Bitcoin Clusters*. USENIX Security 2022. <https://arxiv.org/abs/2205.13882>
