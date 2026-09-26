# H-XCHAIN — Cross-chain exit markers

> **Family:** crosschain · **Status in btc-intel:** planned · **Confidence:** high

## Summary

Cross-chain swap protocols leave markers on Bitcoin. THORChain inbound transactions carry an OP_RETURN memo naming the destination chain, asset and address; outbound transactions reference the inbound transaction's hash. The memo tells an investigator exactly where the funds went on the other chain.

## How it works

THORChain memo grammar [thorchain-memos]:

| Function | Format | Aliases |
|---|---|---|
| Swap | `SWAP:ASSET:DESTADDR:LIM/INTERVAL/QUANTITY:AFFILIATE:FEE` | `s`, `=`, `=<` |
| Add liquidity | `ADD:POOL:PAIREDADDR:AFFILIATE:FEE` | `a`, `+` |
| Withdraw | `WITHDRAW:POOL:BASISPOINTS:ASSET` | `wd`, `-` |
| Donate | `DONATE:POOL` | `d` |
| Outbound / refund | `OUT:<inbound hash>` / `REFUND:<inbound hash>` | — |

Example memo: `=:ETH.ETH:0xe6a30f4f3bad978910e2cbb4d97581f5b5a0ade0`, a swap to ETH delivered to that Ethereum address. On Bitcoin the memo must fit the 80-byte OP_RETURN limit [thorchain-memos]. In 2025 the Bybit proceeds were moved from ETH to BTC largely through THORChain [trm-bybit-2025]. Omni Layer payloads (legacy USDT) start with the ASCII bytes `omni`.

## Signals and thresholds

- A printable-ASCII OP_RETURN that parses as a THORChain memo whose asset has the `CHAIN.ASSET` (or `~`/`/`) form, or an `OUT`/`REFUND` with a 64-hex hash.
- An OP_RETURN starting with `omni`.
- Bridge, Chainflip and instant-exchanger deposits are recognised through address tags instead.

## False positives and limitations

- Arbitrary text that happens to look like a memo is rejected unless the asset has the CHAIN.ASSET form.

## Evasion / countermeasures

Protocols without memos (Chainflip deposit channels, bridges) need address attribution.

## Detection in btc-intel

Findings `thorchain:<action>` (swap, add, withdraw, donate, outbound, refund) with asset and destination, and `omni_layer`.

Planned — Plan 2 implements this in `backend/btcintel/heuristics/crosschain.py`.

## Case examples

[I-2025-BYBIT](../incidents/i-2025-bybit.md), [I-2024-DMM](../incidents/i-2024-dmm.md).

## References

- [thorchain-memos] — (2026). *THORChain developer docs: Transaction Memos*. <https://dev.thorchain.org/concepts/memos.html>
- [trm-bybit-2025] TRM Labs (2025). *Bybit Hack Update: North Korea Moves to Next Stage of Laundering*. <https://www.trmlabs.com/resources/blog/bybit-hack-update-north-korea-moves-to-next-stage-of-laundering>
