# I-2026-LIQUID — Liquid Network federation peg exploit

> **Date:** 2026-09-06 · **Loss:** ~4,000 BTC withdrawn (~$320M); ~3,400 BTC returned · **Attribution:** unknown (Self-described white-hat hackers)

## Summary

On 6 September 2026 attackers exploited a bug in Elements to mint L-BTC without a matching BTC deposit, exchanged it through SideSwap and withdrew about 4,000 BTC (~$320M) from the Liquid federation wallet [coindesk-liquid-2026][chainalysis-liquid-2026]. Calling themselves white hats, they returned about 3,400 BTC and kept about 598.5 BTC.

## How it works

[O-PROTOCOL-EXPLOIT](../techniques/o-protocol-exploit.md) in a sidechain's peg mechanism ([O-SIDECHAIN](../techniques/o-sidechain.md)) [chainalysis-liquid-2026].

## Laundering timeline

- 6 September 2026: unbacked L-BTC minted and redeemed via peg-out [coindesk-liquid-2026].
- Following days: negotiation and partial return of funds [chainalysis-liquid-2026].

Technique chain: [O-PROTOCOL-EXPLOIT](../techniques/o-protocol-exploit.md) (Protocol or platform bug exploitation) → [O-SIDECHAIN](../techniques/o-sidechain.md) (Sidechains (Liquid)).

## Signals and thresholds

- Peg-outs from federation addresses not matched by peg-ins; large withdrawals shortly after unusual sidechain activity.

## Detection in btc-intel

Seeds:

No published Bitcoin seeds yet: The cited reports do not list the peg-out transactions; Blockstream's incident report or the federation's peg-out records could supply them.

No seeds yet; the peg-out transactions would be traced forward to follow the retained ~598.5 BTC.

## Case examples

Bridges and pegs concentrate risk in custody logic; accounting invariants (minted ≤ deposited) must be enforced.

## References

- [coindesk-liquid-2026] — (2026). *$320 million bitcoin exploit hits Liquid Network. Hacker makes conditional offer*. <https://www.coindesk.com/markets/2026/09/07/bitcoin-network-used-by-exchanges-hit-by-usd320-million-exploit-hackers-claim-they-re-the-good-guys>
- [chainalysis-liquid-2026] Chainalysis (2026). *How The $320M Exploit of Liquid Network Went Down*. <https://www.chainalysis.com/blog/320m-exploit-liquid-network/>
