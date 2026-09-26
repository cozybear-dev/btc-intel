# H-PUBKEY — Public-key reuse across scripts

> **Family:** clustering · **Status in btc-intel:** planned · **Confidence:** medium

## Summary

The same public key can appear under different address formats or inside multisig scripts. Recognising the key links those addresses even when they never co-spend.

## How it works

- A P2PKH address and a native SegWit P2WPKH address derived from the same public key commit to the same 20-byte HASH160 of that key, so the two addresses can be linked by comparing the hash, even before either is spent.
- Once spent, inputs reveal public keys in their scriptSig or witness, and multisig redeem or witness scripts reveal every cosigner key. A service reusing a cosigner key across many multisig wallets links them all.
- General background on address and key reuse is in the Bitcoin Wiki's privacy article [bitcoinwiki-privacy].

## Signals and thresholds

- Identical HASH160 across P2PKH/P2WPKH addresses.
- Identical public keys revealed in spends of different addresses.
- Shared keys inside multisig scripts.

## False positives and limitations

- Third-party cosigners (collaborative-custody providers) appear in the multisig scripts of many unrelated customers; their key must not be treated as ownership.

## Evasion / countermeasures

Fresh keys per address, and Taproot key-path spends, which hide multisig structure ([O-SCRIPT-PRIVACY](../techniques/o-script-privacy.md)).

## Detection in btc-intel

This needs an index of revealed public keys across the chain, which the whole-chain phase (spec Phase 3) provides.

Planned for a later phase (not part of Plan 2); see the notes above for what it needs.

## Case examples

No public case study is attached to this technique yet.

## References

- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
