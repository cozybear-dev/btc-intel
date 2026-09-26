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

**Dogfood traces (2026-09-26).** Run with `--hops 4 --max-calls 300` against mempool.space, with tags imported from mining pools, OFAC, GraphSense and ransomwhe.re. Taint is haircut unless noted.

- On chain, the seed address received 70.3446 BTC at 2025-04-27 21:09 UTC (`98d2786d…828d`) and 3,449.9993 BTC at 21:15 UTC (`e5f8962a…cc97`): 3,520.34 BTC, matching the published total.
- The thief reuses the theft address as change: `156a50b8…d59e` (21:25 UTC) sends 3,449.9993 BTC and returns 3,139.7927 BTC to it; `64a0a0ba…4e00` (21:33 UTC) sends 3,139.7927 BTC and returns 350.3569 BTC; `24f71612…2ea6` (21:57 UTC) sends 357.4022 BTC. The bulk leaves to `bc1qhy88fu2wdyc8hkcky9vq9hn42m9vtjp7688f0y`.
- Because change detection follows the self-change output, `--peel` records the large transfers to `bc1qhy88…` (2,789.4 and 310.2 BTC) as peel-offs and follows the shrinking remainder. For the bulk, use the plain forward trace: `btcintel trace bc1qcrypchnrdx87jnal5e5m849fw460t4gk7vz55g --hops 4 --max-calls 300` (36 transactions, complete; its stops account for the full 3,520.34 BTC) ends at hop 4 with 1,981.3 BTC at `bc1qhy88…` (1,713.8 + 267.5), 572.3 BTC at `bc1q7x45glnt2xhdhfes2v26y9ecastyhyw0ep3c7a` and 427.8 BTC at `bc1qnjtecjmg7ar44lncmhnzzjy5y45v4zgw3fyc3l`.
- No instant-exchange exit is tagged in the imported sets, so the Monero swaps are not reached as labeled exits.

## Case examples

Swapping to Monero quickly ends public-ledger tracing; speed matters for freezes at swap services.

## References

- [cryptoslate-330m-2025] — (2025). *ZachXBT tracks $330M Bitcoin stolen in social engineering scam from elderly American*. <https://cryptoslate.com/zachxbt-tracks-330m-bitcoin-stolen-in-social-engineering-scam-from-elderly-american/>
- [zachxbt-330m-2025] ZachXBT (2025). *Post reporting the 3,520 BTC ($330.7M) theft and its theft address*. <https://x.com/zachxbt/status/1916756932763046273>
