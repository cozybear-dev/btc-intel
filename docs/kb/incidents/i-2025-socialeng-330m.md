# I-2025-SOCIALENG-330M — $330M social-engineering theft from an elderly holder

> **Date:** 2025-04-28 · **Loss:** 3,520 BTC (~$330.7M) · **Attribution:** unknown

## Summary

On 28 April 2025, 3,520 BTC (about $330.7M) was stolen from an elderly U.S. holder through social engineering [cryptoslate-330m-2025]. ZachXBT published the theft address `bc1qcrypchnrdx87jnal5e5m849fw460t4gk7vz55g` [zachxbt-330m-2025].

## How it works

[O-SOCIAL-ENGINEERING](../techniques/o-social-engineering.md) against an individual holder [cryptoslate-330m-2025].

## Laundering timeline

- 28 April 2025: 3,520 BTC moved to the theft address [zachxbt-330m-2025].
- Hours later: laundering via a peel chain ([O-PEEL-CHAIN](../techniques/o-peel-chain.md)) through more than six instant exchanges ([O-INSTANT-SWAP](../techniques/o-instant-swap.md)) into Monero ([O-PRIVACY-COIN](../techniques/o-privacy-coin.md)), briefly lifting Monero's price about 50% [cryptoslate-330m-2025].

Technique chain: [O-SOCIAL-ENGINEERING](../techniques/o-social-engineering.md) (Victim social engineering) → [O-PEEL-CHAIN](../techniques/o-peel-chain.md) (Peel chains) → [O-INSTANT-SWAP](../techniques/o-instant-swap.md) (Instant exchangers) → [O-PRIVACY-COIN](../techniques/o-privacy-coin.md) (Swaps into privacy coins).

## Signals and thresholds

- A peel chain ([H-PEEL](../heuristics/h-peel.md)) whose peels land at instant-exchanger deposits.

## Detection in btc-intel

Seeds:

| Kind | Value | Role | Note | Source |
|---|---|---|---|---|
| address | `bc1qcrypchnrdx87jnal5e5m849fw460t4gk7vz55g` | theft | Theft address published by ZachXBT | [zachxbt-330m-2025] |

Trace forward from the theft address in peel mode: `btcintel trace bc1qcrypchnrdx87jnal5e5m849fw460t4gk7vz55g --peel --hops 10 --max-calls 400`.

## Case examples

Swapping to Monero quickly ends public-ledger tracing; speed matters for freezes at swap services.

## References

- [cryptoslate-330m-2025] — (2025). *ZachXBT tracks $330M Bitcoin stolen in social engineering scam from elderly American*. <https://cryptoslate.com/zachxbt-tracks-330m-bitcoin-stolen-in-social-engineering-scam-from-elderly-american/>
- [zachxbt-330m-2025] ZachXBT (2025). *Post reporting the 3,520 BTC ($330.7M) theft and its theft address*. <https://x.com/zachxbt/status/1916756932763046273>
