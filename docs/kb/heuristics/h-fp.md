# H-FP — Wallet fingerprinting

> **Family:** fingerprint · **Status in btc-intel:** planned · **Confidence:** medium

## Summary

Wallet software leaves recognisable traces in the fields and construction choices of the transactions it builds. Fingerprints narrow down which wallet produced a transaction and link transactions made by the same wallet. Misra reports guessing the originating wallet for about 50% of recent transactions with a few heuristics [misra2024].

## How it works

| Trait | Typical values | What it suggests |
|---|---|---|
| nVersion | 1, 2 (3 for TRUC) | wallet generation and defaults |
| nLockTime | 0, a recent block height (anti-fee-sniping), a timestamp | wallets that set nLockTime near the current tip use anti-fee-sniping |
| nSequence | 0xffffffff (final), 0xfffffffe, 0xfffffffd | any input below 0xfffffffe signals opt-in replace-by-fee [bip125] |
| Ordering | BIP69 lexicographic, random, fixed change position | BIP69 users sort inputs and outputs [bip69] |
| Signatures | every ECDSA signature ≤ 71 bytes including the sighash byte | low-R grinding (an R value without the leading zero byte) |
| Script types | P2PKH, P2SH-P2WPKH, P2WPKH, P2TR, mixtures | supported and default address types |
| Public keys | 65-byte uncompressed keys | old wallets |
| Fee rate | integer sat/vB vs. arbitrary | fee estimation and manual entry |

Misra classifies fingerprints as independent (nVersion, anti-fee-sniping, script types, RBF), probabilistic (BIP69, low-R grinding, input order) and dependent (change position and type) [misra2024]. The DFRWS 2025 study of a tumbler shows fingerprints at work: across 22 mixing sessions the tumbler's payouts carried rare combinations of nVersion, nLockTime and nSequence, which made its supposedly ordinary-looking transactions recognisable [dfrws2025tumbler].

## Signals and thresholds

- btc-intel records all traits above for every non-coinbase transaction.
- It computes a stable *signature* over nVersion, locktime style, RBF and input script types, used by [H-CHG-FPCONT](h-chg-fpcont.md).
- Anti-fee-sniping is reported when nLockTime is a height 1–2016 blocks below the confirmation height.

## False positives and limitations

- Popular wallets share defaults, so a fingerprint rarely identifies a wallet uniquely from one transaction.
- Low-R grinding cannot be inferred from a single signature, because about half of all signatures are low-R by chance.

## Evasion / countermeasures

Fingerprint mimicry, randomised fields and Taproot ([O-CHANGE-AVOIDANCE](../techniques/o-change-avoidance.md), [O-SCRIPT-PRIVACY](../techniques/o-script-privacy.md)).

## Detection in btc-intel

Planned — Plan 2 implements this in `backend/btcintel/heuristics/fingerprint.py`.

## Case examples

The DFRWS 2025 tumbler study [dfrws2025tumbler].

## References

- [misra2024] Ishaana Misra (2024). *Wallet Fingerprints: Detection & Analysis*. <https://ishaana.com/blog/wallet_fingerprinting/>
- [dfrws2025tumbler] — (2025). *Tumbling down the stairs: Exploiting a tumbler's attempt to hide with ordinary-looking transactions using wallet fingerprinting*. Forensic Science International: Digital Investigation 52 (DFRWS EU 2025). <https://www.sciencedirect.com/science/article/pii/S2666281725000083>
- [bip69] — (2015). *BIP69: Lexicographical Indexing of Transaction Inputs and Outputs*. <https://github.com/bitcoin/bips/blob/master/bip-0069.mediawiki>
- [bip125] — (2015). *BIP125: Opt-in Full Replace-by-Fee Signaling*. <https://github.com/bitcoin/bips/blob/master/bip-0125.mediawiki>
