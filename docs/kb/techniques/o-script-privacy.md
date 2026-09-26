# O-SCRIPT-PRIVACY — Protocol privacy features

> **Tactic:** Obfuscation · **OAK:** — · **FATF red-flag areas:** anonymity

## Summary

Taproot hides multisig and scripts behind single keys, Silent Payments (BIP352) and BIP47 payment codes avoid address reuse, reducing script- and reuse-based linking.

Examples: Taproot key-path spends, Silent Payments, BIP47 PayNyms.

## How it works

- Taproot (BIP341) lets complex spending conditions be spent via a single-key path, so multisig and contracts can look like ordinary single-signature spends [bip341].
- BIP47 reusable payment codes and Silent Payments (BIP352) let a recipient publish one static identifier while every payment lands on a fresh address [bip47][bip352].

## Signals and thresholds

- Fewer revealed scripts and public keys; no reusable receive address.
- Fingerprints ([H-FP](../heuristics/h-fp.md)) still expose the wallet type.

Detected by: [H-FP](../heuristics/h-fp.md). Evades: [H-REUSE](../heuristics/h-reuse.md), [H-PUBKEY](../heuristics/h-pubkey.md), [H-FP](../heuristics/h-fp.md).

## False positives and limitations

—

## Evasion / countermeasures

—

## Detection in btc-intel

Script types are part of every fingerprint; payment-code notification transactions and Silent Payments scanning are not detected.

## Case examples

—

## References

- [bip341] — (2020). *BIP341: Taproot: SegWit version 1 spending rules*. <https://github.com/bitcoin/bips/blob/master/bip-0341.mediawiki>
- [bip352] — (2023). *BIP352: Silent Payments*. <https://github.com/bitcoin/bips/blob/master/bip-0352.mediawiki>
- [bip47] — (2015). *BIP47: Reusable Payment Codes for Hierarchical Deterministic Wallets*. <https://github.com/bitcoin/bips/blob/master/bip-0047.mediawiki>
