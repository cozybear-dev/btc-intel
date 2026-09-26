# O-PRIVACY-COIN — Swaps into privacy coins

> **Tactic:** Chain hopping · **OAK:** OAK-T7.005 · **FATF red-flag areas:** anonymity

## Summary

BTC is swapped into Monero (often via instant exchangers), ending public-ledger traceability (the $243M 2024 and $330M 2025 thefts). Detection relies on tags of the swap services used.

Examples: $243M Genesis-creditor theft 2024, $330M theft 2025.

## How it works

Swapping into Monero ends public-ledger tracing: "once funds are swapped into Monero, tracing becomes virtually impossible", and the 2025 theft's conversion moved Monero's price by about 50% [cryptoslate-330m-2025]. The 2024 Genesis-creditor theft was routed through exchanges and swap services [theblock-genesis-2024]. FATF lists anonymity-enhanced cryptocurrencies among its red flags [fatf2020redflags].

## Signals and thresholds

- The Bitcoin side ends at an instant-exchanger or P2P deposit.

Detected by: —. Evades: —.

## False positives and limitations

—

## Evasion / countermeasures

—

## Detection in btc-intel

Out of scope beyond the Bitcoin exit: the trace stops at the tagged swap service.

## Case examples

[I-2024-GENESIS-CREDITOR](../incidents/i-2024-genesis-creditor.md), [I-2025-SOCIALENG-330M](../incidents/i-2025-socialeng-330m.md).

## References

- [theblock-genesis-2024] — (2024). *Blockchain sleuth ZachXBT alleges three attackers involved in $243 million theft of single Genesis creditor*. <https://www.theblock.co/post/317349/blockchain-sleuth-zachxbt-alleges-three-perps-involved-in-243-million-theft-of-single-genesis-creditor>
- [cryptoslate-330m-2025] — (2025). *ZachXBT tracks $330M Bitcoin stolen in social engineering scam from elderly American*. <https://cryptoslate.com/zachxbt-tracks-330m-bitcoin-stolen-in-social-engineering-scam-from-elderly-american/>
- [fatf2020redflags] FATF (2020). *Virtual Assets Red Flag Indicators of Money Laundering and Terrorist Financing*. <https://www.fatf-gafi.org/content/dam/fatf-gafi/reports/Virtual-Assets-Red-Flag-Indicators.pdf>
