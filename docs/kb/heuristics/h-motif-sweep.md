# H-MOTIF-SWEEP — Mass key-compromise sweep

> **Family:** pattern · **Status in btc-intel:** planned · **Confidence:** medium

## Summary

When keys are generated with too little entropy, attackers can recompute them offline and sweep every affected wallet within minutes. The on-chain signature is a burst of transactions emptying many unrelated, often long-dormant, single-signature addresses into a few attacker addresses.

## How it works

- **Coldcard Mk3 (July 2026)**: in the first wave about 1,082 BTC was swept from about 1,196 addresses in 41 minutes. All the wallets were single-signature, each held more than 0.15 BTC, and many had been dormant for years [coindesk-coldcard-2026].
- **Milk Sad (2023)**: Libbitcoin Explorer's `bx seed` derived seeds from 32 bits of system time. The researchers confirmed use of the weak function in over 2,600 mainnet wallets and linked it to thefts of about $900k [milksad-2023].
- **LuBian (December 2020)**: Arkham reports that more than 90% of the mining pool's BTC was drained on 28 December 2020, attributing the breach to weak private-key generation [arkham-lubian-2025].

## Signals and thresholds

- Many sweeps within a short window from addresses with no prior common-input links, converging on few destinations.
- Prevout ages (dormancy) and address types are strong supporting evidence.

## False positives and limitations

- A service migrating its own wallets produces similar bursts, but usually from addresses already clustered together.

## Evasion / countermeasures

Attackers can stagger sweeps over time.

## Detection in btc-intel

Needs prevout ages and cross-transaction timing windows, planned for the whole-chain phase.

Planned for a later phase (not part of Plan 2); see the notes above for what it needs.

## Case examples

[I-2026-COLDCARD](../incidents/i-2026-coldcard.md), [I-2023-MILKSAD](../incidents/i-2023-milksad.md), [I-2020-LUBIAN](../incidents/i-2020-lubian.md).

## References

- [coindesk-coldcard-2026] — (2026). *How bitcoin cold wallets lost $70 million in an attack that never touched the devices*. <https://www.coindesk.com/tech/2026/08/01/how-bitcoin-cold-wallets-lost-usd70-million-in-an-attack-that-never-touched-the-devices>
- [milksad-2023] — (2023). *Milk Sad: /bx full write-up (CVE-2023-39910)*. <https://milksad.info/disclosure.html>
- [arkham-lubian-2025] Arkham Intelligence (2025). *Arkham Uncovers $3.5B Heist - the Largest Ever*. <https://info.arkm.com/announcements/arkham-uncovers>
