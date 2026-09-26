# H-CORR — Amount/time correlation across services

> **Family:** pattern · **Status in btc-intel:** planned · **Confidence:** medium

## Summary

Custodial mixers and instant swappers pay out amounts close to the deposit minus a fee, within a limited time window. Matching amounts and times across the service boundary can re-link deposits and withdrawals.

## How it works

The DFRWS 2025 tumbler study recorded the tumbler's deposit and payout transactions over 22 sessions and showed that its payouts are distinguishable, making correlation tractable [dfrws2025tumbler].

## Signals and thresholds

- Payout value ≈ deposit value × (1 − fee) within Δt.
- Payout transaction fingerprints that differ from the service's ordinary payouts.

## False positives and limitations

- High-volume services see many similar amounts in any window.

## Evasion / countermeasures

Random delays, split payouts and variable fees.

## Detection in btc-intel

Needs labelled service address sets and time-windowed value matching.

Planned for a later phase (not part of Plan 2); see the notes above for what it needs.

## Case examples

No public case study is attached to this technique yet.

## References

- [dfrws2025tumbler] — (2025). *Tumbling down the stairs: Exploiting a tumbler's attempt to hide with ordinary-looking transactions using wallet fingerprinting*. Forensic Science International: Digital Investigation 52 (DFRWS EU 2025). <https://www.sciencedirect.com/science/article/pii/S2666281725000083>
