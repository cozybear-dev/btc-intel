# O-LIGHTNING — Lightning Network

> **Tactic:** Off-chain / layer 2 · **OAK:** — · **FATF red-flag areas:** anonymity

## Summary

Funds enter payment channels (visible only as channel open/close on chain) and move off-chain, including via submarine swaps. Detection relies on tags of known node and swap-service addresses; channel-funding detection is planned under H-XCHAIN.

Examples: private channels, submarine swaps.

## How it works

Funds enter a payment channel with an on-chain funding transaction and leave with a closing transaction; payments in between happen off chain [lightning-bolts].

## Signals and thresholds

- Channel funding outputs (2-of-2 multisig P2WSH, or Taproot) and closes.
- Submarine-swap service deposits.

Detected by: —. Evades: —.

## False positives and limitations

—

## Evasion / countermeasures

Private (unannounced) channels.

## Detection in btc-intel

btc-intel stops a trace at addresses tagged with a stop category and reports the stop as `labeled`; importing good tags (`btcintel import-tags ...`) is what makes this technique visible. Channel-funding detection is planned under H-XCHAIN.

## Case examples

—

## References

- [lightning-bolts] — (2024). *BOLT: Basis of Lightning Technology (Lightning Network specifications)*. <https://github.com/lightning/bolts>
