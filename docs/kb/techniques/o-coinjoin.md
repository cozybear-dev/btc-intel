# O-COINJOIN — Non-custodial CoinJoin

> **Tactic:** Obfuscation · **OAK:** OAK-T7.001 · **FATF red-flag areas:** anonymity

## Summary

Users jointly build transactions with equal outputs so input→output links are ambiguous (Wasabi 2.x on community coordinators such as kruw.io, Ashigaru Whirlpool, JoinMarket/Jam).

Examples: Wasabi 2.x, Ginger, Ashigaru Whirlpool, JoinMarket.

## How it works

```
 many users' inputs ─► one transaction ─► equal-value outputs (+ change) ─► remixes / spends
```
Coordinator history:
- zkSNACKs, which ran Wasabi's default coordinator, discontinued the service in June 2024 citing regulatory pressure; Wasabi removed its own CoinJoin fees in version 2.2.0.0 and lets users pick independent coordinators [atlas21-coinjoin-2026].
- Samourai Wallet's founders were arrested in April 2024 and charged over its Whirlpool and Ricochet services [doj-samourai-2024].
- Ashigaru relaunched Whirlpool in June 2025 with two pools, 0.025 and 0.25 BTC, each with a 5% anti-Sybil fee [atlas21-coinjoin-2026].
- The original JoinMarket repository was archived on 27 April 2026; joinmarket-ng and the Jam web UI continue [atlas21-coinjoin-2026].
- The PoPETs 2026 study analyses the Wasabi 1.x, Wasabi 2.x and Whirlpool coordinator ecosystems [popets2026coinjoin].

## Signals and thresholds

- Implementation-specific structures ([H-CJ](../heuristics/h-cj.md) and children).
- Post-mix leaks ([H-CJ-POST](../heuristics/h-cj-post.md)).

Detected by: [H-CJ](../heuristics/h-cj.md), [H-CJ-POST](../heuristics/h-cj-post.md). Evades: [H-CIOH](../heuristics/h-cioh.md), [H-CHG](../heuristics/h-chg.md).

## False positives and limitations

- Batch payouts with repeated amounts can resemble generic CoinJoins (low confidence).

## Evasion / countermeasures

Remixing and careful post-mix coin control.

## Detection in btc-intel

CoinJoins are classified per transaction; CIOH and change detection are suppressed for them, and traces stop at them (`coinjoin` stop) unless run with `coinjoin=through`, which spreads taint across all outputs by haircut.

## Case examples

—

## References

- [popets2026coinjoin] — (2026). *CoinJoin ecosystem insights for Wasabi 1.x, Wasabi 2.x and Whirlpool coordinator-based privacy mixers*. PoPETs 2026. <https://petsymposium.org/popets/2026/popets-2026-0061.php>
- [atlas21-coinjoin-2026] — (2026). *CoinJoin in 2026: Wasabi, JoinMarket and Ashigaru compared*. <https://atlas21.com/coinjoin-comparison-of-tools-to-improve-privacy-on-bitcoin/>
- [doj-samourai-2024] U.S. Attorney's Office SDNY (2024). *Founders And CEO Of Cryptocurrency Mixing Service Arrested And Charged With Money Laundering And Unlicensed Money Transmitting Offenses*. <https://www.justice.gov/usao-sdny/pr/founders-and-ceo-cryptocurrency-mixing-service-arrested-and-charged-money-laundering>
