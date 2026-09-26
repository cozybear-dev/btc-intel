# O-CHANGE-AVOIDANCE — Change-heuristic evasion

> **Tactic:** Obfuscation · **OAK:** — · **FATF red-flag areas:** anonymity

## Summary

Exact-amount spends without change, change matching the payee's script type, randomised ordering, non-round payments and fingerprint mimicry defeat change detection.

Examples: branch-and-bound coin selection, script-type matching, fingerprint mimicry.

## How it works

Wallets and users defeat change detection by paying exact amounts from well-chosen coins so that no change is created, generating change with the payee's script type, randomising output order, avoiding round payment amounts, and mimicking the fingerprints of other wallets [bitcoinwiki-privacy][misra2024].

## Signals and thresholds

- Few or conflicting change signals; [H-CHG](../heuristics/h-chg.md) then reports no change instead of guessing.
- Fingerprint continuity ([H-CHG-FPCONT](../heuristics/h-chg-fpcont.md)) can still expose the change because the wallet spends it later.

Detected by: [H-CHG-FPCONT](../heuristics/h-chg-fpcont.md). Evades: [H-CHG](../heuristics/h-chg.md), [H-FP](../heuristics/h-fp.md).

## False positives and limitations

—

## Evasion / countermeasures

—

## Detection in btc-intel

The change detector requires a probability of at least 0.6 and a unique winner, so conflicting signals yield "undetermined" instead of a wrong link.

## Case examples

—

## References

- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
- [misra2024] Ishaana Misra (2024). *Wallet Fingerprints: Detection & Analysis*. <https://ishaana.com/blog/wallet_fingerprinting/>
