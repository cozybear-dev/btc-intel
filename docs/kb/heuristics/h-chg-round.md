# H-CHG-ROUND — Round payment amount

> **Family:** change · **Status in btc-intel:** implemented · **Confidence:** medium · **Parent:** [H-CHG](h-chg.md)

## Summary

People pay round amounts; change is whatever is left over. When every output but one is round, the ragged output is probably change.

## How it works

The Bitcoin Wiki: "Many payment amounts are round numbers, for example 1 BTC or 0.1 BTC. The leftover change amount would then be a non-round number" [bitcoinwiki-privacy]. Round amounts denominated in fiat at the time of payment are a variant (not yet implemented).

Example: an input of 250,000 sats pays 100,000 sats and 149,000 sats. 100,000 has five trailing zeros (round); 149,000 has three (ragged). The 149,000-sat output is probably change (probability ≈ 0.77 on this signal alone).

## Signals and thresholds

- "Round" means at least 5 trailing decimal zeros in satoshis (a multiple of 0.001 BTC); "ragged" means at most 3.
- Exactly one ragged output while every other output is round. Weight +1.2 for the ragged output and −1.2 for each round one.

## False positives and limitations

- Users moving round amounts to themselves.
- Invoices priced in fiat that convert to ragged BTC amounts.

## Evasion / countermeasures

Paying or requesting non-round amounts; [O-CHANGE-AVOIDANCE](../techniques/o-change-avoidance.md).

## Detection in btc-intel

This signal contributes to the [H-CHG](h-chg.md) vote: +1.2 to the only ragged output (≤3 trailing decimal zeros) when every other output is round (≥5 zeros); −1.2 to each round output.

Implemented in `backend/btcintel/heuristics/change.py` (`offline_votes`).

## Case examples

Androulaki et al. discuss how payment amounts help profile users [androulaki2013].

## References

- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
- [androulaki2013] Elli Androulaki, Ghassan Karame, Marc Roeschlin, Tobias Scherer, Srdjan Capkun (2013). *Evaluating User Privacy in Bitcoin*. Financial Cryptography 2013. <https://eprint.iacr.org/2012/596>
