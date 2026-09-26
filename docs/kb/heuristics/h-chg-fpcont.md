# H-CHG-FPCONT — Fingerprint continuity

> **Family:** change · **Status in btc-intel:** implemented · **Confidence:** medium · **Parent:** [H-CHG](h-chg.md)

## Summary

Change is spent later by the same wallet software that created it, so the transaction spending the change usually shares the current transaction's wallet fingerprint. Payment outputs are spent by the recipient's wallet, which often differs.

## How it works

btc-intel reduces a transaction's fingerprint ([H-FP](h-fp.md)) to a signature of wallet-choice traits: nVersion, locktime style, RBF signalling and input script types. It then compares that signature with the signature of the transaction spending each output. Misra documents that wallets differ in exactly these traits [misra2024]; Kappos et al. show that following the same entity's spends (peel chains) validates clusters [kappos2022].

Example: a version-2, RBF-signalling transaction pays two outputs. Output 1 is later spent by another version-2, RBF-signalling transaction with the same input types, while output 0 is spent by a version-1 transaction. Output 1 gains +1.0 and output 0 gains −0.3, so output 1 is reported as change (probability ≈ 0.73).

## Signals and thresholds

- The spending transaction's fingerprint signature equals this transaction's. Weight +1.0; −0.3 when it differs.
- Needs the outspends and the spending transactions, costing one extra API call per output.

## False positives and limitations

- Payer and payee using the same popular wallet with default settings produce identical signatures.

## Evasion / countermeasures

Fingerprint mimicry and randomised transaction fields ([O-CHANGE-AVOIDANCE](../techniques/o-change-avoidance.md)).

## Detection in btc-intel

This signal contributes to the [H-CHG](h-chg.md) vote: needs a chain: +1.0 when the output's spending tx has the same fingerprint signature, −0.3 otherwise.

Implemented in `backend/btcintel/heuristics/change.py` (`fingerprint_votes`).

## Case examples

No public case study is attached to this technique yet.

## References

- [misra2024] Ishaana Misra (2024). *Wallet Fingerprints: Detection & Analysis*. <https://ishaana.com/blog/wallet_fingerprinting/>
- [kappos2022] George Kappos, Haaroon Yousaf, Rainer Stütz, Sofia Rollet, Bernhard Haslhofer, Sarah Meiklejohn (2022). *How to Peel a Million: Validating and Expanding Bitcoin Clusters*. USENIX Security 2022. <https://arxiv.org/abs/2205.13882>
