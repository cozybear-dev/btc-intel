# O-ECASH — Chaumian e-cash mints

> **Tactic:** Off-chain / layer 2 · **OAK:** — · **FATF red-flag areas:** anonymity

## Summary

Fedimint federations and Cashu mints issue blinded e-cash tokens against BTC, so transfers inside the mint are unlinkable. Detection relies on tags of mint addresses.

Examples: Fedimint, Cashu.

## How it works

Chaumian e-cash mints (Fedimint federations, Cashu mints) issue blinded tokens against deposited BTC; transfers of tokens inside the mint are unlinkable [fedimint][cashu].

## Signals and thresholds

- Deposits to and withdrawals from mint addresses.

Detected by: —. Evades: —.

## False positives and limitations

—

## Evasion / countermeasures

—

## Detection in btc-intel

btc-intel stops a trace at addresses tagged with a stop category and reports the stop as `labeled`; importing good tags (`btcintel import-tags ...`) is what makes this technique visible.

## Case examples

—

## References

- [fedimint] — (2024). *Fedimint*. <https://fedimint.org/>
- [cashu] — (2024). *Cashu: Chaumian ecash for Bitcoin*. <https://cashu.space/>
