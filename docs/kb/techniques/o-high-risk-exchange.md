# O-HIGH-RISK-EXCHANGE — High-risk exchanges

> **Tactic:** Integration (cash-out) · **OAK:** — · **FATF red-flag areas:** senders_recipients, geographical

## Summary

Exchanges with no or weak KYC/AML that knowingly serve criminals (BTC-e laundered Mt. Gox proceeds; Garantex processed ≥$96B before its 2025 takedown). Detection relies on tags.

Examples: BTC-e, Garantex, Grinex, Bitzlato.

## How it works

- BTC-e's operator pleaded guilty to money-laundering conspiracy; the exchange is linked to laundering proceeds of the Mt. Gox hack [doj-btce-2024].
- Garantex's infrastructure was taken down in March 2025; it had processed at least $96 billion since 2019 and was alleged to serve criminal organisations and sanctions evasion [doj-garantex-2025].

## Signals and thresholds

- Deposits to addresses tagged `high_risk_exchange` or sanctioned (risk severe).

Detected by: —. Evades: —.

## False positives and limitations

—

## Evasion / countermeasures

Successor services (e.g. Grinex after Garantex) need fresh tags.

## Detection in btc-intel

btc-intel stops a trace at addresses tagged with a stop category and reports the stop as `labeled`; importing good tags (`btcintel import-tags ...`) is what makes this technique visible.

## Case examples

[I-2011-MTGOX](../incidents/i-2011-mtgox.md).

## References

- [doj-btce-2024] U.S. Department of Justice (2024). *BTC-e Operator Pleads Guilty to Money Laundering Conspiracy*. <https://www.justice.gov/archives/opa/pr/btc-e-operator-pleads-guilty-money-laundering-conspiracy>
- [doj-garantex-2025] U.S. Department of Justice (2025). *Garantex Cryptocurrency Exchange Disrupted in International Operation*. <https://www.justice.gov/opa/pr/garantex-cryptocurrency-exchange-disrupted-international-operation>
