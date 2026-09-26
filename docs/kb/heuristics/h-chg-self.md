# H-CHG-SELF — Change returned to an input address

> **Family:** change · **Status in btc-intel:** implemented · **Confidence:** high · **Parent:** [H-CHG](h-chg.md)

## Summary

An output paying back to one of the transaction's own input addresses is the change.

## How it works

Some wallets return change to the address they are spending from. The owner already controls that address, so it is almost certainly change.

Example: an input of 100,000 sats from address A pays 30,000 sats to B and 69,000 sats back to A (fee 1,000). The 69,000-sat output to A is change.

## Signals and thresholds

- An output address equals one of the input addresses. Weight +4.0 (probability ≈ 0.98 on its own).

## False positives and limitations

- Shared or custodial addresses used by several parties.
- Deliberate self-payments that are not change.

## Evasion / countermeasures

Wallets that always derive a fresh change address remove the signal entirely.

## Detection in btc-intel

This signal contributes to the [H-CHG](h-chg.md) vote: +4.0 to an output paying an input address.

Implemented in `backend/btcintel/heuristics/change.py` (`offline_votes`).

## Case examples

No public case study is attached to this technique yet.

## References

- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
