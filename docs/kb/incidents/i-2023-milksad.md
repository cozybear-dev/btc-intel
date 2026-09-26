# I-2023-MILKSAD — Milk Sad (Libbitcoin Explorer bx seed) weak-entropy thefts

> **Date:** 2023-07-12 · **Loss:** Estimated ~$900k across multiple chains · **Attribution:** unknown

## Summary

Libbitcoin Explorer 3.x's `bx seed` command generated wallet entropy with a Mersenne Twister seeded from 32 bits of system time (CVE-2023-39910), making the resulting keys brute-forceable. The researchers confirmed use of the weak function in over 2,600 Bitcoin mainnet wallets and linked it to thefts estimated at about $900k across several blockchains [milksad-2023].

## How it works

[O-WEAK-KEY-SWEEP](../techniques/o-weak-key-sweep.md): an attacker enumerates all 2³² possible seeds, derives the wallets and sweeps any that hold funds [milksad-2023].

## Laundering timeline

- From about May 2023: small-scale exploitation [milksad-2023].
- Around 12 July 2023: the main theft [milksad-2023].
- August 2023: public disclosure [milksad-2023].

Technique chain: [O-WEAK-KEY-SWEEP](../techniques/o-weak-key-sweep.md) (Weak key-generation exploitation).

## Signals and thresholds

- Coordinated sweeps of many unrelated wallets within a short window ([H-MOTIF-SWEEP](../heuristics/h-motif-sweep.md)).

## Detection in btc-intel

Seeds:

No published Bitcoin seeds yet: The public write-up describes the affected wallet population without listing specific theft addresses; the researchers' datasets could supply them.

No seeds yet; the researchers' wallet datasets could supply them.

## Case examples

Wallet-generation tooling is part of the attack surface; weak entropy is exploitable at scale years later.

## References

- [milksad-2023] — (2023). *Milk Sad: /bx full write-up (CVE-2023-39910)*. <https://milksad.info/disclosure.html>
