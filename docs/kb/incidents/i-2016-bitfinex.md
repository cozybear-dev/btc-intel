# I-2016-BITFINEX — Bitfinex hack and laundering (Lichtenstein & Morgan)

> **Date:** 2016-08-02 · **Loss:** 119,754 BTC stolen; more than 94,000 BTC recovered in 2022 · **Attribution:** confirmed (Ilya Lichtenstein (hacker), assisted in laundering by Heather Morgan)

## Summary

In 2016 Ilya Lichtenstein breached Bitfinex and fraudulently authorised more than 2,000 transactions moving 119,754 BTC to a wallet he controlled [doj-bitfinex-2022]. In February 2022 agents obtained files with the wallet's private keys and seized more than 94,000 BTC [doj-bitfinex-2022], consolidated into one address that received about 94,643 BTC [merkle-bitfinex-2022]. Lichtenstein and Heather Morgan pleaded guilty in 2023; Lichtenstein was sentenced in 2024 [doj-bitfinex-2024].

## How it works

[O-KEY-COMPROMISE](../techniques/o-key-compromise.md): compromise of the exchange's systems, followed by thousands of fraudulent withdrawal authorisations [doj-bitfinex-2022].

## Laundering timeline

- August 2016: 119,754 BTC moved in more than 2,000 transactions [doj-bitfinex-2022][merkle-bitfinex-2022].
- January 2017: a large portion moved to AlphaBay, used as a mixer by depositing and withdrawing equivalent amounts ([O-DARKNET-AS-MIXER](../techniques/o-darknet-as-mixer.md)) [chainalysis-bitfinex-2023].
- 2017–2021: laundering with fictitious-identity accounts ([O-FAKE-KYC](../techniques/o-fake-kyc.md)), automated transactions, deposits and withdrawals at darknet markets and exchanges, chain hopping to other cryptocurrencies ([O-CHAIN-HOP](../techniques/o-chain-hop.md)), mixing services and conversion into gold coins [doj-bitfinex-2024].
- April 2021: about 12,230 BTC moved from 36 addresses [merkle-bitfinex-2022].
- February 2022: seizure of the remaining ~94,643 BTC [merkle-bitfinex-2022].

Technique chain: [O-KEY-COMPROMISE](../techniques/o-key-compromise.md) (Key or signing-infrastructure compromise) → [O-PEEL-CHAIN](../techniques/o-peel-chain.md) (Peel chains) → [O-DISPERSAL](../techniques/o-dispersal.md) (Dispersal and structuring) → [O-DARKNET-AS-MIXER](../techniques/o-darknet-as-mixer.md) (Darknet markets and gambling sites as mixers) → [O-CHAIN-HOP](../techniques/o-chain-hop.md) (Cross-chain bridges and swap protocols) → [O-FAKE-KYC](../techniques/o-fake-kyc.md) (Fraudulent identities and money mules) → [O-DORMANCY](../techniques/o-dormancy.md) (Dormancy and delayed laundering).

## Signals and thresholds

- Thousands of outputs from the theft, long chains of hops ([H-PEEL](../heuristics/h-peel.md)), dispersal ([H-MOTIF-FANOUT](../heuristics/h-motif-fanout.md)), later consolidation ([H-MOTIF-FANIN](../heuristics/h-motif-fanin.md)) and long dormancy.

## Detection in btc-intel

Seeds:

| Kind | Value | Role | Note | Source |
|---|---|---|---|---|
| address | `bc1qazcm763858nkj2dj986etajv6wquslv8uxwczt` | seizure | Consolidation address that received the ~94,643 BTC recovered by the U.S. government (February 2022) | [merkle-bitfinex-2022] |

Trace **backward** from the seizure address to reach the theft-era wallets: `btcintel trace bc1qazcm763858nkj2dj986etajv6wquslv8uxwczt --backward --hops 4 --max-calls 400`. The address has 183 transactions, so expect the call budget to bound the result.

**Dogfood traces (2026-09-26).** Run with `--hops 4 --max-calls 300` against mempool.space, with tags imported from mining pools, OFAC, GraphSense and ransomwhe.re. Taint is haircut unless noted.

- The address seed does not reach the theft-era wallets: `btcintel trace bc1qazcm763858nkj2dj986etajv6wquslv8uxwczt --backward --hops 4 --max-calls 300` starts from the address's newest 50 transactions (`max_address_txs`), which are all small deposits made after the seizure, and ends at 13 `max_hops` and 37 `min_value` stops holding under 0.0005 BTC each.
- The seizure is nine receipts of 2,000–15,000 BTC on 2022-02-01 (84,500 BTC together; for example `9d069942…ffb3`, 15,000 BTC). Seed a backward trace from one of them: `btcintel trace 9d06994238d0de958033f42db39a6d2cc0de35e84be0ed080e41f017f02dffb3 --backward --hops 4 --max-calls 300`. It hits the 200-transaction cap (incomplete, `max_txs`) inside P2SH wallets used in June–August 2016, such as `36FwMjBRMm1Jp6PZoS2qb7zo33a5AT1naW` (2,038.7 BTC at hop 4) and `3HNSiAq7wFDaPsYDcUxNSRMD78qVcYKicw` (337.8 BTC).
- This trace exposed a false positive in [H-CJ-GENERIC](../heuristics/h-cj-generic.md): 2016 batch payouts from these wallets (for example `9ffe06de…a13d`, 13 inputs from one address) were classified as CoinJoins and stopped the trace. The single-actor guard and the output-structure bound now reject them, and four are regression fixtures.
- None of these addresses has a tag in the imported sets, so no `labeled` exit is reached; attributing the 2016 wallets needs analyst tags.

## Case examples

Most of the loot was never laundered; private keys held in cloud storage enabled the recovery [doj-bitfinex-2022]. Darknet markets act as custodial mixers.

## References

- [doj-bitfinex-2022] U.S. Department of Justice (2022). *Two Arrested for Alleged Conspiracy to Launder $4.5 Billion in Stolen Cryptocurrency*. <https://www.justice.gov/archives/opa/pr/two-arrested-alleged-conspiracy-launder-45-billion-stolen-cryptocurrency>
- [doj-bitfinex-2024] U.S. Attorney's Office for the District of Columbia (2024). *Bitfinex Hacker Sentenced in Money Laundering Conspiracy Involving Billions in Stolen Cryptocurrency*. <https://www.justice.gov/usao-dc/pr/bitfinex-hacker-sentenced-money-laundering-conspiracy-involving-billions-stolen>
- [chainalysis-bitfinex-2023] Chainalysis (2023). *Bitfinex Hack Money Launderers Plead Guilty*. <https://www.chainalysis.com/blog/bitfinex-hack-plea-july-2023/>
- [merkle-bitfinex-2022] Merkle Science (2022). *Hack Track: Bitfinex Hack (2016) Recent Fund Movement Analysis*. <https://www.merklescience.com/blog/hack-track-bitfinex-hack-2016-recent-fund-movement-analysis>
