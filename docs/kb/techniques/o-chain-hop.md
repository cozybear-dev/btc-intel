# O-CHAIN-HOP — Cross-chain bridges and swap protocols

> **Tactic:** Chain hopping · **OAK:** OAK-T7.003 · **FATF red-flag areas:** anonymity, transaction_patterns

## Summary

Value is moved to another chain through THORChain, Chainflip or bridges (Avalanche BTC.b, WBTC, tBTC) to break single-chain tracing (DMM 2024, Bybit 2025).

Examples: THORChain, Chainflip, Avalanche Bridge, Threshold tBTC, renBridge (defunct).

## How it works

```
 BTC ─► bridge / swap-protocol vault (memo: destination chain + address) ─► asset on another chain
```
After the Bybit theft, the ETH was largely bridged into BTC through THORChain [trm-bybit-2025]. DMM Bitcoin proceeds were reportedly mixed, bridged onward with THORChain, Avalanche Bridge and Threshold, swapped to USDT and moved to Tron [cybernews-dmm-2024]. THORChain swaps from Bitcoin carry an OP_RETURN memo naming the destination asset and address [thorchain-memos].

## Signals and thresholds

- THORChain memos (`=:ETH.ETH:0x…`, `OUT:<hash>`) → [H-XCHAIN](../heuristics/h-xchain.md).
- Deposits to tagged bridge vaults (category `bridge`).

Detected by: [H-XCHAIN](../heuristics/h-xchain.md). Evades: —.

## False positives and limitations

- Legitimate swaps.

## Evasion / countermeasures

Protocols without memos need address attribution.

## Detection in btc-intel

`thorchain:<action>` findings reveal the destination chain and address; traces stop at `bridge`-tagged addresses. Following funds onto other chains is spec Phase 4.

## Case examples

[I-2025-BYBIT](../incidents/i-2025-bybit.md), [I-2024-DMM](../incidents/i-2024-dmm.md).

## References

- [thorchain-memos] — (2026). *THORChain developer docs: Transaction Memos*. <https://dev.thorchain.org/concepts/memos.html>
- [trm-bybit-2025] TRM Labs (2025). *Bybit Hack Update: North Korea Moves to Next Stage of Laundering*. <https://www.trmlabs.com/resources/blog/bybit-hack-update-north-korea-moves-to-next-stage-of-laundering>
- [cybernews-dmm-2024] — (2024). *Lazarus caught laundering millions from DMM bitcoin hack, some funds frozen*. <https://cybernews.com/crypto/lazarus-caught-laundering-millions-from-dmm/>
