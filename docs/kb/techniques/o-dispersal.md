# O-DISPERSAL — Dispersal and structuring

> **Tactic:** Layering · **OAK:** — · **FATF red-flag areas:** transaction_patterns

## Summary

Proceeds are split across hundreds to thousands of addresses in uniform amounts to overwhelm investigators and stay under monitoring thresholds (Bybit BTC dispersed to ~11,000 addresses).

Examples: Bybit 2025.

## How it works

```
 stolen BTC ─► fan-out ─► hundreds–thousands of addresses (similar amounts) ─► later consolidation / cash-out
```
After the Bybit theft, the funds converted to BTC were dispersed across about 11,000 addresses, which complicated tracking; the laundering proceeded at an unprecedented rate [trm-bybit-2025][dlnews-bybit-2025].

## Signals and thresholds

- Few-input, many-output transactions with uniform values → `dispersal_uniform` ([H-MOTIF-FANOUT](../heuristics/h-motif-fanout.md)); later many-input consolidations ([H-MOTIF-FANIN](../heuristics/h-motif-fanin.md)).

Detected by: [H-MOTIF-FANOUT](../heuristics/h-motif-fanout.md), [H-MOTIF-FANIN](../heuristics/h-motif-fanin.md). Evades: —.

## False positives and limitations

- Exchange batch withdrawals (usually varied amounts).

## Evasion / countermeasures

Varying amounts and spreading dispersal over time.

## Detection in btc-intel

Forward traces follow every branch above `min_value_sats`, highest taint first; the call budget bounds the work and marks the result incomplete when exhausted.

## Case examples

[I-2025-BYBIT](../incidents/i-2025-bybit.md), [I-2016-BITFINEX](../incidents/i-2016-bitfinex.md).

## References

- [trm-bybit-2025] TRM Labs (2025). *Bybit Hack Update: North Korea Moves to Next Stage of Laundering*. <https://www.trmlabs.com/resources/blog/bybit-hack-update-north-korea-moves-to-next-stage-of-laundering>
- [dlnews-bybit-2025] — (2025). *North Korea laundering $1.5bn Bybit hack at 'unprecedented rate'*. <https://www.dlnews.com/articles/defi/how-north-korea-is-laundering-the-bybit-hack/>
