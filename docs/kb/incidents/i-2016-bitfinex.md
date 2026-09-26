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

## Case examples

Most of the loot was never laundered; private keys held in cloud storage enabled the recovery [doj-bitfinex-2022]. Darknet markets act as custodial mixers.

## References

- [doj-bitfinex-2022] U.S. Department of Justice (2022). *Two Arrested for Alleged Conspiracy to Launder $4.5 Billion in Stolen Cryptocurrency*. <https://www.justice.gov/archives/opa/pr/two-arrested-alleged-conspiracy-launder-45-billion-stolen-cryptocurrency>
- [doj-bitfinex-2024] U.S. Attorney's Office for the District of Columbia (2024). *Bitfinex Hacker Sentenced in Money Laundering Conspiracy Involving Billions in Stolen Cryptocurrency*. <https://www.justice.gov/usao-dc/pr/bitfinex-hacker-sentenced-money-laundering-conspiracy-involving-billions-stolen>
- [chainalysis-bitfinex-2023] Chainalysis (2023). *Bitfinex Hack Money Launderers Plead Guilty*. <https://www.chainalysis.com/blog/bitfinex-hack-plea-july-2023/>
- [merkle-bitfinex-2022] Merkle Science (2022). *Hack Track: Bitfinex Hack (2016) Recent Fund Movement Analysis*. <https://www.merklescience.com/blog/hack-track-bitfinex-hack-2016-recent-fund-movement-analysis>
