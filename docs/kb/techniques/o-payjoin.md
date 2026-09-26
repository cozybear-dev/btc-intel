# O-PAYJOIN — Steganographic multi-party transactions

> **Tactic:** Obfuscation · **OAK:** — · **FATF red-flag areas:** anonymity

## Summary

PayJoin (BIP78, BIP77 async), Stowaway and Stonewall-X2 make a payment where the receiver contributes an input, so the transaction looks ordinary but violates CIOH and the unnecessary- input change heuristic.

Examples: BIP78 PayJoin, BIP77 async payjoin, Stowaway, Stonewall-X2.

## How it works

```
 payer input ─┐            ┌─► payee (payment + payee's own input value)
 payee input ─┴─► tx ──────┴─► payer change
```
In a PayJoin (BIP78, and the asynchronous BIP77) the receiver contributes an input to the payment, so the transaction looks like an ordinary payment while its inputs belong to two parties [bip78][bip77]. This breaks the common-input-ownership assumption, which the Bitcoin Wiki notes CoinJoin-like constructions are designed to do [bitcoinwiki-privacy]. Stowaway and Stonewall-X2 are wallet-specific variants.

## Signals and thresholds

- Hard to detect by design. Weak hints: inputs of mixed script types, or an input that violates the unnecessary-input rule.
- Stonewall's structure is detected by [H-CJ-STONEWALL](../heuristics/h-cj-stonewall.md).

Detected by: [H-CJ-STONEWALL](../heuristics/h-cj-stonewall.md). Evades: [H-CIOH](../heuristics/h-cioh.md), [H-CHG-UNNECESSARY](../heuristics/h-chg-unnecessary.md).

## False positives and limitations

- Hints fire on ordinary transactions too.

## Evasion / countermeasures

—

## Detection in btc-intel

Only the Stonewall structure is detected. PayJoins that look like payments are an accepted blind spot of CIOH, which is why clusters record the evidence for every link.

## Case examples

—

## References

- [bip78] — (2020). *BIP78: A Simple Payjoin Proposal*. <https://github.com/bitcoin/bips/blob/master/bip-0078.mediawiki>
- [bip77] — (2023). *BIP77: Async Payjoin*. <https://github.com/bitcoin/bips/blob/master/bip-0077.md>
- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
