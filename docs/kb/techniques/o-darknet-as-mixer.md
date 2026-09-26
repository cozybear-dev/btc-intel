# O-DARKNET-AS-MIXER — Darknet markets and gambling sites as mixers

> **Tactic:** Obfuscation · **OAK:** — · **FATF red-flag areas:** anonymity, senders_recipients

## Summary

Funds are deposited to and withdrawn from custodial darknet-market or gambling accounts, which breaks the on-chain link like a mixer (AlphaBay in the Bitfinex laundering). Detection relies on address tags of those services.

Examples: AlphaBay (Bitfinex laundering).

## How it works

```
 stolen BTC ─► darknet-market deposit ─► (custodial balance) ─► withdrawal to new address
```
The Bitfinex launderers deposited stolen funds into accounts at darknet markets and exchanges and then withdrew them [doj-bitfinex-2022][doj-bitfinex-2024]. In January 2017 a large portion moved to the AlphaBay market, which the couple effectively used as a mixer, depositing stolen bitcoin and withdrawing equivalent amounts [chainalysis-bitfinex-2023]. FATF lists transfers involving darknet marketplaces among its red flags [fatf2020redflags].

## Signals and thresholds

- Deposits to addresses tagged as darknet markets or gambling services, and withdrawals of similar amounts shortly after.

Detected by: —. Evades: —.

## False positives and limitations

- Ordinary customers of the same services.

## Evasion / countermeasures

—

## Detection in btc-intel

btc-intel stops a trace at addresses tagged with a stop category and reports the stop as `labeled`; importing good tags (`btcintel import-tags ...`) is what makes this technique visible.

## Case examples

[I-2016-BITFINEX](../incidents/i-2016-bitfinex.md).

## References

- [doj-bitfinex-2022] U.S. Department of Justice (2022). *Two Arrested for Alleged Conspiracy to Launder $4.5 Billion in Stolen Cryptocurrency*. <https://www.justice.gov/archives/opa/pr/two-arrested-alleged-conspiracy-launder-45-billion-stolen-cryptocurrency>
- [doj-bitfinex-2024] U.S. Attorney's Office for the District of Columbia (2024). *Bitfinex Hacker Sentenced in Money Laundering Conspiracy Involving Billions in Stolen Cryptocurrency*. <https://www.justice.gov/usao-dc/pr/bitfinex-hacker-sentenced-money-laundering-conspiracy-involving-billions-stolen>
- [chainalysis-bitfinex-2023] Chainalysis (2023). *Bitfinex Hack Money Launderers Plead Guilty*. <https://www.chainalysis.com/blog/bitfinex-hack-plea-july-2023/>
- [fatf2020redflags] FATF (2020). *Virtual Assets Red Flag Indicators of Money Laundering and Terrorist Financing*. <https://www.fatf-gafi.org/content/dam/fatf-gafi/reports/Virtual-Assets-Red-Flag-Indicators.pdf>
