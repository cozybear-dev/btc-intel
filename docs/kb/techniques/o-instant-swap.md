# O-INSTANT-SWAP — Instant exchangers

> **Tactic:** Chain hopping · **OAK:** — · **FATF red-flag areas:** anonymity

## Summary

Account-less swap services convert BTC into other assets with little or no KYC (eXch until its 2025 closure, FixedFloat, SideShift, ChangeNOW). Detection relies on address tags of the services plus amount/time correlation.

Examples: eXch, FixedFloat, SideShift, ChangeNOW.

## How it works

```
 BTC ─► instant-exchanger deposit address ─► (off-chain swap) ─► XMR / other asset to a new address
```
The Bybit laundering used swap services including eXch [dlnews-bybit-2025]. The 2025 $330 million theft passed through more than six instant exchanges before becoming Monero [cryptoslate-330m-2025].

## Signals and thresholds

- Deposits to addresses tagged `instant_exchange`.
- Amount and time correlation with the other side of the swap ([H-CORR](../heuristics/h-corr.md)).

Detected by: [H-CORR](../heuristics/h-corr.md). Evades: —.

## False positives and limitations

- Ordinary users of the same services.

## Evasion / countermeasures

Services rotate deposit addresses.

## Detection in btc-intel

btc-intel stops a trace at addresses tagged with a stop category and reports the stop as `labeled`; importing good tags (`btcintel import-tags ...`) is what makes this technique visible.

## Case examples

[I-2025-BYBIT](../incidents/i-2025-bybit.md), [I-2025-SOCIALENG-330M](../incidents/i-2025-socialeng-330m.md), [I-2024-GENESIS-CREDITOR](../incidents/i-2024-genesis-creditor.md).

## References

- [dlnews-bybit-2025] — (2025). *North Korea laundering $1.5bn Bybit hack at 'unprecedented rate'*. <https://www.dlnews.com/articles/defi/how-north-korea-is-laundering-the-bybit-hack/>
- [cryptoslate-330m-2025] — (2025). *ZachXBT tracks $330M Bitcoin stolen in social engineering scam from elderly American*. <https://cryptoslate.com/zachxbt-tracks-330m-bitcoin-stolen-in-social-engineering-scam-from-elderly-american/>
