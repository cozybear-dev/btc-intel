# O-SIDECHAIN — Sidechains (Liquid)

> **Tactic:** Off-chain / layer 2 · **OAK:** — · **FATF red-flag areas:** anonymity

## Summary

Peg-in to Liquid moves BTC into a federation wallet; confidential transactions hide amounts and assets on the sidechain until peg-out. Detection relies on tags of federation addresses.

Examples: Liquid Network.

## How it works

A peg-in moves BTC into the Liquid federation's wallet; on the sidechain, confidential transactions hide amounts and assets until a peg-out returns BTC. The September 2026 exploit drained about 4,000 BTC from the federation wallet by redeeming unbacked L-BTC [chainalysis-liquid-2026][coindesk-liquid-2026].

## Signals and thresholds

- Deposits to, and withdrawals from, tagged federation addresses.

Detected by: —. Evades: —.

## False positives and limitations

—

## Evasion / countermeasures

—

## Detection in btc-intel

btc-intel stops a trace at addresses tagged with a stop category and reports the stop as `labeled`; importing good tags (`btcintel import-tags ...`) is what makes this technique visible.

## Case examples

[I-2026-LIQUID](../incidents/i-2026-liquid.md).

## References

- [chainalysis-liquid-2026] Chainalysis (2026). *How The $320M Exploit of Liquid Network Went Down*. <https://www.chainalysis.com/blog/320m-exploit-liquid-network/>
- [coindesk-liquid-2026] — (2026). *$320 million bitcoin exploit hits Liquid Network. Hacker makes conditional offer*. <https://www.coindesk.com/markets/2026/09/07/bitcoin-network-used-by-exchanges-hit-by-usd320-million-exploit-hackers-claim-they-re-the-good-guys>
