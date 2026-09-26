# H-REUSE — Address reuse

> **Family:** clustering · **Status in btc-intel:** kb_only · **Confidence:** high

## Summary

Receiving several payments at one address links them all to the same owner and exposes the owner's balance and counterparties. Nakamoto recommended a new key pair for every transaction precisely to avoid this [nakamoto2008].

## How it works

An address is a public identifier. Every payment to it, and every spend from it, is visible and trivially linkable. The Bitcoin Wiki also uses reuse for change detection: "If an output address has been reused it is very likely to be a payment output, not a change output" [bitcoinwiki-privacy].

## Signals and thresholds

- The same address appears as an output (or input) in more than one transaction.

## False positives and limitations

- Shared deposit addresses of custodial services and publicly posted donation addresses aggregate many unrelated payers.

## Evasion / countermeasures

Fresh addresses per payment (HD wallets), BIP47 payment codes and Silent Payments ([O-SCRIPT-PRIVACY](../techniques/o-script-privacy.md)).

## Detection in btc-intel

Address reuse needs no detector in btc-intel: addresses are graph nodes, so all transactions touching a reused address attach to the same node.

Knowledge-base only: btc-intel does not implement this as an automated detector.

## Case examples

No public case study is attached to this technique yet.

## References

- [nakamoto2008] Satoshi Nakamoto (2008). *Bitcoin: A Peer-to-Peer Electronic Cash System*. <https://bitcoin.org/bitcoin.pdf>
- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
