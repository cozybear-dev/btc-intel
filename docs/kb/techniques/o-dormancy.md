# O-DORMANCY — Dormancy and delayed laundering

> **Tactic:** Layering · **OAK:** — · **FATF red-flag areas:** transaction_patterns

## Summary

Stolen coins are left untouched for months or years before being moved, waiting for attention to fade (Silk Road/Zhong, Bitfinex, LuBian).

Examples: Silk Road/Zhong 2012–2021, Bitfinex 2016–2022, LuBian 2020–2025.

## How it works

- Zhong's Silk Road proceeds (taken in 2012) were seized from devices in his home in November 2021 [doj-zhong-2022].
- Bitfinex's stolen coins (2016) were largely recovered in 2022, when agents obtained files holding the private keys of the wallet that received them and seized more than 94,000 BTC [doj-bitfinex-2022].
- LuBian's 2020 theft went unnoticed for nearly five years [arkham-lubian-2025].

## Signals and thresholds

- Coins untouched for months or years, then moved ([H-TEMPORAL](../heuristics/h-temporal.md)).

Detected by: [H-TEMPORAL](../heuristics/h-temporal.md). Evades: —.

## False positives and limitations

- Long-term holders ("HODLers") moving old coins.

## Evasion / countermeasures

—

## Detection in btc-intel

Planned: dormancy flags need prevout ages. Watchlists in case files let analysts monitor known theft addresses.

## Case examples

[I-2012-SILKROAD](../incidents/i-2012-silkroad.md), [I-2016-BITFINEX](../incidents/i-2016-bitfinex.md), [I-2020-LUBIAN](../incidents/i-2020-lubian.md).

## References

- [doj-zhong-2022] U.S. Attorney's Office SDNY (2022). *U.S. Attorney Announces Historic $3.36 Billion Cryptocurrency Seizure And Conviction In Connection With Silk Road Dark Web Fraud*. <https://www.justice.gov/usao-sdny/pr/us-attorney-announces-historic-336-billion-cryptocurrency-seizure-and-conviction>
- [doj-bitfinex-2022] U.S. Department of Justice (2022). *Two Arrested for Alleged Conspiracy to Launder $4.5 Billion in Stolen Cryptocurrency*. <https://www.justice.gov/archives/opa/pr/two-arrested-alleged-conspiracy-launder-45-billion-stolen-cryptocurrency>
- [arkham-lubian-2025] Arkham Intelligence (2025). *Arkham Uncovers $3.5B Heist - the Largest Ever*. <https://info.arkm.com/announcements/arkham-uncovers>
