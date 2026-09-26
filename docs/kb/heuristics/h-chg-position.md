# H-CHG-POSITION — Output ordering

> **Family:** change · **Status in btc-intel:** planned · **Confidence:** low · **Parent:** [H-CHG](h-chg.md)

## Summary

Some wallets place change at a fixed output index. Combined with wallet identification this hints at the change output; BIP69 ordering removes the signal.

## How it works

BIP69 sorts inputs and outputs lexicographically so that output position carries no information [bip69]. Wallets that do not use BIP69 may consistently put change first or last, or shuffle it; the Bitcoin Wiki discusses ordering as a privacy leak [bitcoinwiki-privacy].

## Signals and thresholds

- Wallet-specific change position combined with a fingerprint-based wallet guess ([H-FP](h-fp.md)).

## False positives and limitations

- BIP69 or randomised ordering.

## Evasion / countermeasures

BIP69 or random output ordering.

## Detection in btc-intel

Needs per-wallet ground truth on change position, which is not yet collected.

Planned for a later phase (not part of Plan 2); see the notes above for what it needs.

## Case examples

No public case study is attached to this technique yet.

## References

- [bip69] — (2015). *BIP69: Lexicographical Indexing of Transaction Inputs and Outputs*. <https://github.com/bitcoin/bips/blob/master/bip-0069.mediawiki>
- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
