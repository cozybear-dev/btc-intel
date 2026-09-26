# O-RICOCHET — Hop padding (Ricochet)

> **Tactic:** Layering · **OAK:** — · **FATF red-flag areas:** anonymity

## Summary

Several intermediate self-transfers are inserted before the destination so that shallow (1–2 hop) exchange screening sees no direct exposure (Samourai's Ricochet service).

Examples: Samourai Ricochet.

## How it works

```
 wallet ─► hop 1 ─► hop 2 ─► hop 3 ─► hop 4 ─► destination (e.g. an exchange)
```
Prosecutors described Samourai's Ricochet service as adding multiple transaction "hops" to make tracing more difficult; together, Whirlpool and Ricochet were alleged to have handled more than $2 billion of transactions and earned about $4.5 million in fees [doj-samourai-2024].

## Signals and thresholds

- Short chains of single-input, single-output (or peel-like) self-transfers immediately before a service deposit.
- Multi-hop exposure: [H-TAINT](../heuristics/h-taint.md) keeps taint through extra hops that a 1–2-hop screen would miss; [H-PEEL](../heuristics/h-peel.md).

Detected by: [H-TAINT](../heuristics/h-taint.md), [H-PEEL](../heuristics/h-peel.md). Evades: —.

## False positives and limitations

- Wallet housekeeping transactions.

## Evasion / countermeasures

—

## Detection in btc-intel

Backward traces from a deposit follow any number of hops up to `max_hops`, so padding adds only a few API calls.

## Case examples

—

## References

- [doj-samourai-2024] U.S. Attorney's Office SDNY (2024). *Founders And CEO Of Cryptocurrency Mixing Service Arrested And Charged With Money Laundering And Unlicensed Money Transmitting Offenses*. <https://www.justice.gov/usao-sdny/pr/founders-and-ceo-cryptocurrency-mixing-service-arrested-and-charged-money-laundering>
