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

**Dogfood traces (2026-09-26).** Run with `--hops 4 --max-calls 300` against mempool.space, with tags imported from mining pools, OFAC, GraphSense and ransomwhe.re. Taint is haircut unless noted.

- Both theft transactions pay the same thief address, `bc1q7ev96n4rv4rut09kfew4a8h5xg9l5hj68maf3p` (59.3422 + 14.8816 BTC). In `e747b963…` the victim's own address receives the 0.3577 BTC change ([H-CHG-SELF](../heuristics/h-chg-self.md), p = 0.982), so `--peel` seeded with the txid follows the victim. Seed the stolen outpoint instead: `btcintel trace e747b963a463334c164b0a8fff844f73693272bb2b331adbe2147d70ec196360:0 --hops 4 --max-calls 300`.
- Within 47 minutes the thief moves everything to `bc1q4epwxygm5uuw3zmpz897w8lat6x34r3xkc7yqs`: 59.30 BTC in `9d80b7d2…48d9` (02:06 UTC, with 0.0422 BTC change back to the thief address, so peel mode records the 59.30 BTC as a peel-off) and a sweep of that change plus the 14.88 BTC in `b8e3705f…5217` (02:35 UTC).
- From the outpoint, the trace ends at hop 4 with 45.72 BTC at `bc1q7ma9gapqn9kfsj4s3fhxzhumy3rmjvdgtfwvxr` and 10.39 BTC at `1K6kEipEumbkUPFRYJpa4PsQtLYUsXqw7L`. From the second theft (`btcintel trace 7c7ebed785f0b4d4335d559b14b8215862fbe29db329e3ee0f2a7e64a16ce9e3 --hops 4 --max-calls 300`, 53 transactions) one labeled exit is reached: `bc1qr4dl5wa7kl8yu792dceg9z5knl2gkn220lk7a9` (exchange, "crypto.com reserves wallets", 0.0305 BTC).
- An earlier run stopped at `fb86c4cf…1883` as a generic CoinJoin; it splits four inputs from one address into six equal 15.14 BTC outputs, and the corrected [H-CJ-GENERIC](../heuristics/h-cj-generic.md) rule no longer flags it.
- The instant exchanges named in the published analysis are not tagged in the imported sets.

## Case examples

Social engineering bypasses cryptography; the laundering spread was wide, but exchange cooperation still froze part of the funds.

## References

- [theblock-genesis-2024] — (2024). *Blockchain sleuth ZachXBT alleges three attackers involved in $243 million theft of single Genesis creditor*. <https://www.theblock.co/post/317349/blockchain-sleuth-zachxbt-alleges-three-perps-involved-in-243-million-theft-of-single-genesis-creditor>
- [zachxbt-genesis-2024] ZachXBT (2024). *Thread on the $243M theft from a Genesis creditor (incident summary and theft transactions)*. <https://x.com/zachxbt/status/1836752940029149269>
