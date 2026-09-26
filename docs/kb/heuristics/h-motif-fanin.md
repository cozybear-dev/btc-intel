# H-MOTIF-FANIN — Fan-in / consolidation

> **Family:** pattern · **Status in btc-intel:** planned · **Confidence:** medium

## Summary

A transaction with many inputs and one or two outputs: a consolidation. Services sweep deposit addresses this way; launderers consolidate after dispersal; post-mix consolidation re-links mixed coins.

## How it works

Consolidations are strong clustering evidence ([H-CIOH](h-cioh.md)) and often mark a service sweeping customer deposits into a hot wallet [meiklejohn2013].

## Signals and thresholds

- At least 10 inputs and at most 2 spendable outputs; not a multi-party CoinJoin. Confidence 0.6.

## False positives and limitations

- Routine wallet UTXO consolidation at low fee rates.

## Evasion / countermeasures

Avoiding consolidation (keeping many small UTXOs).

## Detection in btc-intel

Planned — Plan 2 implements this in `backend/btcintel/heuristics/patterns.py`.

## Case examples

No public case study is attached to this technique yet.

## References

- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
