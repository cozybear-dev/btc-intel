# I-2024-GENESIS-CREDITOR — $243M social-engineering theft from a Genesis creditor

> **Date:** 2024-08-19 · **Loss:** 4,064 BTC (~$243M) · **Attribution:** suspected (Three alleged perpetrators identified by ZachXBT (two later arrested))

## Summary

On 19 August 2024 attackers stole 4,064 BTC (about $243M) from a single Genesis creditor [theblock-genesis-2024]. ZachXBT's thread lays out the social-engineering sequence and includes theft transactions such as 59.34 BTC at 01:48 UTC and 14.88 BTC at 02:30 UTC [zachxbt-genesis-2024]. Two suspects were later arrested.

## How it works

[O-SOCIAL-ENGINEERING](../techniques/o-social-engineering.md): the attackers posed as Google support, then as Gemini support, persuaded the victim to reset two-factor authentication, and used remote-access software to obtain private keys [theblock-genesis-2024].

## Laundering timeline

- 19 August 2024: wallet drained in several transactions [zachxbt-genesis-2024].
- Following days: funds routed through more than 15 exchanges and swap services ([O-INSTANT-SWAP](../techniques/o-instant-swap.md)), part swapped to Monero ([O-PRIVACY-COIN](../techniques/o-privacy-coin.md)) [theblock-genesis-2024].

Technique chain: [O-SOCIAL-ENGINEERING](../techniques/o-social-engineering.md) (Victim social engineering) → [O-INSTANT-SWAP](../techniques/o-instant-swap.md) (Instant exchangers) → [O-PRIVACY-COIN](../techniques/o-privacy-coin.md) (Swaps into privacy coins).

## Signals and thresholds

- A long-held personal wallet emptied in a few large transactions, then deposits at instant exchangers ([H-PEEL](../heuristics/h-peel.md), address tags).

## Detection in btc-intel

Seeds:

| Kind | Value | Role | Note | Source |
|---|---|---|---|---|
| tx | `e747b963a463334c164b0a8fff844f73693272bb2b331adbe2147d70ec196360` | theft | 59.34 BTC theft transaction, 19 Aug 2024 01:48 UTC | [zachxbt-genesis-2024] |
| tx | `7c7ebed785f0b4d4335d559b14b8215862fbe29db329e3ee0f2a7e64a16ce9e3` | theft | 14.88 BTC theft transaction, 19 Aug 2024 02:30 UTC | [zachxbt-genesis-2024] |

Trace forward from either theft transaction, stopping at `instant_exchange` and `exchange` tags: `btcintel trace e747b963a463334c164b0a8fff844f73693272bb2b331adbe2147d70ec196360 --hops 5`.

## Case examples

Social engineering bypasses cryptography; the laundering spread was wide, but exchange cooperation still froze part of the funds.

## References

- [theblock-genesis-2024] — (2024). *Blockchain sleuth ZachXBT alleges three attackers involved in $243 million theft of single Genesis creditor*. <https://www.theblock.co/post/317349/blockchain-sleuth-zachxbt-alleges-three-perps-involved-in-243-million-theft-of-single-genesis-creditor>
- [zachxbt-genesis-2024] ZachXBT (2024). *Thread on the $243M theft from a Genesis creditor (incident summary and theft transactions)*. <https://x.com/zachxbt/status/1836752940029149269>
