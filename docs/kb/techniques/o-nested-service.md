# O-NESTED-SERVICE — Nested services and exchange deposit layering

> **Tactic:** Integration (cash-out) · **OAK:** OAK-T7.002 · **FATF red-flag areas:** senders_recipients, transaction_patterns

## Summary

Launderers deposit through accounts of other services hosted at a large exchange, or structure deposits across many exchange accounts to avoid thresholds. Detection relies on exchange tags and deposit-cluster analysis.

Examples: nested exchange accounts, structured CEX deposits.

## How it works

```
 launderer ─► accounts at a nested service / many CEX accounts ─► exchange deposit addresses ─► hot wallet sweep
```
OAK classifies CEX deposit-address layering as a laundering technique [oak]. FATF red flags include structuring transactions and using accounts that do not match customer profiles [fatf2020redflags].

## Signals and thresholds

- Many small deposits into different deposit addresses of the same exchange cluster; the sweeps are consolidations ([H-MOTIF-FANIN](../heuristics/h-motif-fanin.md)).

Detected by: [H-MOTIF-FANIN](../heuristics/h-motif-fanin.md). Evades: —.

## False positives and limitations

- Ordinary retail deposits.

## Evasion / countermeasures

—

## Detection in btc-intel

btc-intel stops a trace at addresses tagged with a stop category and reports the stop as `labeled`; importing good tags (`btcintel import-tags ...`) is what makes this technique visible. Expanding an exchange's cluster links its deposit addresses through sweeps.

## Case examples

—

## References

- [oak] — (2026). *OAK: OnChain Attack Knowledge framework*. <https://onchainattack.org/>
- [fatf2020redflags] FATF (2020). *Virtual Assets Red Flag Indicators of Money Laundering and Terrorist Financing*. <https://www.fatf-gafi.org/content/dam/fatf-gafi/reports/Virtual-Assets-Red-Flag-Indicators.pdf>
