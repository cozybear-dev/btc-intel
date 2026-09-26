# I-2012-SILKROAD — Silk Road withdrawal exploit (James Zhong)

> **Date:** 2012-09 · **Loss:** ~50,676 BTC seized in 2021 (about 50,000 BTC obtained in 2012) · **Attribution:** confirmed (James Zhong)

## Summary

In September 2012 James Zhong exploited Silk Road's withdrawal processing to obtain about 50,000 BTC. In November 2021 agents seized about 50,676 BTC from devices in his home; he pleaded guilty to wire fraud [doj-zhong-2022].

## How it works

[O-PROTOCOL-EXPLOIT](../techniques/o-protocol-exploit.md): Zhong created at least nine accounts, deposited 200–2,000 BTC in them and triggered more than 140 transactions in rapid succession, tricking the withdrawal system into releasing far more than he had deposited [doj-zhong-2022].

## Laundering timeline

- September 2012: the exploit (many rapid withdrawals) [doj-zhong-2022].
- 2012–2021: the coins stay hidden ([O-DORMANCY](../techniques/o-dormancy.md)).
- November 2021: about 50,676 BTC seized [doj-zhong-2022].

Technique chain: [O-PROTOCOL-EXPLOIT](../techniques/o-protocol-exploit.md) (Protocol or platform bug exploitation) → [O-DORMANCY](../techniques/o-dormancy.md) (Dormancy and delayed laundering).

## Signals and thresholds

- A burst of withdrawals from a single service to a handful of new addresses, then years of dormancy ([H-TEMPORAL](../heuristics/h-temporal.md)).

## Detection in btc-intel

Seeds:

No published Bitcoin seeds yet: The DOJ release does not list Bitcoin addresses; the forfeiture filings could supply them.

No seeds yet (the DOJ release lists none).

## Case examples

Race conditions in custodial withdrawal logic can drain a service; stolen coins may be held untouched for years.

## References

- [doj-zhong-2022] U.S. Attorney's Office SDNY (2022). *U.S. Attorney Announces Historic $3.36 Billion Cryptocurrency Seizure And Conviction In Connection With Silk Road Dark Web Fraud*. <https://www.justice.gov/usao-sdny/pr/us-attorney-announces-historic-336-billion-cryptocurrency-seizure-and-conviction>
