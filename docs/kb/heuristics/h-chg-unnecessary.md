# H-CHG-UNNECESSARY — Unnecessary input

> **Family:** change · **Status in btc-intel:** implemented · **Confidence:** medium · **Parent:** [H-CHG](h-chg.md)

## Summary

Wallets do not add inputs they do not need. If an output is smaller than the smallest input, a single input would have covered it, so that output is probably change and the larger output is the payment.

## How it works

The Bitcoin Wiki's example: with inputs of 2 BTC and 3 BTC and outputs of about 1 BTC and 4 BTC, "if the 1 BTC output is the payment amount then the 3 BTC input is unnecessary, as the wallet could have spent only the 2 BTC input and paid lower miner fees" [bitcoinwiki-privacy].

In satoshis: inputs of 200,000,000 and 300,000,000; outputs of 400,000,000 and 99,990,000. The 99,990,000-sat output is below the smallest input, so it is change.

## Signals and thresholds

- At least two inputs and exactly one output smaller than the smallest input. Weight +1.0.

## False positives and limitations

- Wallets that deliberately add inputs for privacy (PayJoin, Stonewall) or consolidate while paying.

## Evasion / countermeasures

[O-PAYJOIN](../techniques/o-payjoin.md) breaks this signal by design.

## Detection in btc-intel

This signal contributes to the [H-CHG](h-chg.md) vote: +1.0 to the only output smaller than the smallest input, when there are ≥2 inputs.

Implemented in `backend/btcintel/heuristics/change.py` (`offline_votes`).

## Case examples

No public case study is attached to this technique yet.

## References

- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
