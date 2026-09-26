# H-TEMPORAL — Temporal profiling

> **Family:** temporal · **Status in btc-intel:** planned · **Confidence:** low

## Summary

Timing reveals behaviour: hour-of-day histograms hint at an operator's time zone, and long dormancy followed by sudden movement flags funds, often stolen or seized, becoming active.

## How it works

Androulaki et al. combine address clustering with behavioural features of users' transactions to profile them [androulaki2013].

## Signals and thresholds

- Transaction times clustered in a daily window.
- Coins dormant for years, then moved.

## False positives and limitations

- Automated services operate around the clock.
- Block timestamps approximate, but do not equal, broadcast time.

## Evasion / countermeasures

Scheduling transactions randomly.

## Detection in btc-intel

Needs per-cluster timestamp histograms and prevout ages.

Planned for a later phase (not part of Plan 2); see the notes above for what it needs.

## Case examples

Dormancy features in [I-2012-SILKROAD](../incidents/i-2012-silkroad.md) and [I-2016-BITFINEX](../incidents/i-2016-bitfinex.md).

## References

- [androulaki2013] Elli Androulaki, Ghassan Karame, Marc Roeschlin, Tobias Scherer, Srdjan Capkun (2013). *Evaluating User Privacy in Bitcoin*. Financial Cryptography 2013. <https://eprint.iacr.org/2012/596>
