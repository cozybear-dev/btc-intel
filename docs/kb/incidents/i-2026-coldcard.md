# I-2026-COLDCARD — Coldcard Mk3 weak-seed sweeps

> **Date:** 2026-07-30 · **Loss:** ~1,082 BTC in the first wave (CoinDesk); ~1,816 BTC across four waves (TRM) · **Attribution:** unknown

## Summary

A Coldcard firmware build released in March 2021 fell back to a weak software random-number generator, so some Mk3 seeds carried as little as about 40 bits of entropy [trm-coldcard-2026]. From 30 July 2026 an attacker swept affected single-signature wallets without touching the devices. CoinDesk reports about 1,082 BTC from about 1,196 addresses in 41 minutes in the first wave [coindesk-coldcard-2026]; TRM counts about 1,816 BTC across four waves and more than 5,200 addresses, with little laundering so far (for example one 64.9 BTC Wasabi deposit) [trm-coldcard-2026].

## How it works

[O-WEAK-KEY-SWEEP](../techniques/o-weak-key-sweep.md): keys brute-forced offline from low-entropy seeds [coindesk-coldcard-2026][trm-coldcard-2026].

## Laundering timeline

- March 2021: affected firmware released [trm-coldcard-2026].
- 30 July 2026: first sweep wave [coindesk-coldcard-2026].
- Following days: further waves; limited laundering observed [trm-coldcard-2026].

Technique chain: [O-WEAK-KEY-SWEEP](../techniques/o-weak-key-sweep.md) (Weak key-generation exploitation).

## Signals and thresholds

- Many dormant single-sig addresses (each >0.15 BTC) emptied within minutes into few consolidation addresses ([H-MOTIF-SWEEP](../heuristics/h-motif-sweep.md)) [coindesk-coldcard-2026].

## Detection in btc-intel

Seeds:

No published Bitcoin seeds yet: The cited reports do not list sweep or consolidation addresses in their text; investigator address lists or the consolidation transactions could supply seeds.

No seeds yet; add consolidation addresses from investigators' lists, then trace forward.

## Case examples

Firmware entropy bugs can expose wallets years after generation; multisig across vendors is defence in depth.

## References

- [coindesk-coldcard-2026] — (2026). *How bitcoin cold wallets lost $70 million in an attack that never touched the devices*. <https://www.coindesk.com/tech/2026/08/01/how-bitcoin-cold-wallets-lost-usd70-million-in-an-attack-that-never-touched-the-devices>
- [trm-coldcard-2026] TRM Labs (2026). *The Largest Hardware Wallet Exploit of 2026: Inside the USD 116 Million Coldcard Hack*. <https://www.trmlabs.com/resources/blog/the-largest-hardware-wallet-exploit-of-2026-inside-the-usd-116-million-coldcard-hack>
