# O-KEY-COMPROMISE — Key or signing-infrastructure compromise

> **Tactic:** Acquisition · **OAK:** — · **FATF red-flag areas:** source_of_funds

## Summary

Theft by stealing hot-wallet keys or subverting the signing workflow (e.g. the 2025 Bybit Safe{Wallet} UI supply-chain attack, DMM Bitcoin 2024). Tracing starts from the victim's disclosed outflows.

Examples: Mt. Gox 2011–2014, Bitfinex 2016, DMM Bitcoin 2024, Bybit 2025, Bitget 2026.

## How it works

```
 attacker ─► steals keys / subverts signing ─► victim hot wallet ─► attacker addresses ─► laundering
```
- **Bitfinex 2016**: the attacker fraudulently authorised more than 2,000 transactions, moving 119,754 BTC to a wallet under his control [doj-bitfinex-2022].
- **DMM Bitcoin 2024**: 4,502.9 BTC was taken; the laundering pattern and off-chain indicators pointed to North Korea's Lazarus Group [cybernews-dmm-2024].
- **Bybit 2025**: about $1.5 billion in ETH was taken by North Korea's TraderTraitor group [trm-bybit-2025].
- **Bitget 2026**: on 24 September 2026, attackers made unauthorised transfers from several hot wallets totalling about $351.6 million; attribution to Lazarus was still a hypothesis [hackread-bitget-2026].

## Signals and thresholds

- Large, sudden outflows from a known service wallet to fresh addresses, often followed by dispersal ([H-MOTIF-FANOUT](../heuristics/h-motif-fanout.md)) or peel chains ([H-PEEL](../heuristics/h-peel.md)).

Detected by: [H-MOTIF-FANOUT](../heuristics/h-motif-fanout.md), [H-PEEL](../heuristics/h-peel.md). Evades: —.

## False positives and limitations

- Legitimate wallet migrations by the service itself.

## Evasion / countermeasures

Multisig with independent signers, hardware-backed signing, verification of what is actually being signed, and monitoring for anomalous outflows.

## Detection in btc-intel

Tracing starts from the victim's disclosed theft transactions: `btcintel trace <txid>` forward, usually with a stop at exchanges and bridges. Incident seeds are in `catalog/incidents/`.

## Case examples

[I-2016-BITFINEX](../incidents/i-2016-bitfinex.md), [I-2024-DMM](../incidents/i-2024-dmm.md), [I-2025-BYBIT](../incidents/i-2025-bybit.md), [I-2026-BITGET](../incidents/i-2026-bitget.md), [I-2011-MTGOX](../incidents/i-2011-mtgox.md).

## References

- [doj-bitfinex-2022] U.S. Department of Justice (2022). *Two Arrested for Alleged Conspiracy to Launder $4.5 Billion in Stolen Cryptocurrency*. <https://www.justice.gov/archives/opa/pr/two-arrested-alleged-conspiracy-launder-45-billion-stolen-cryptocurrency>
- [cybernews-dmm-2024] — (2024). *Lazarus caught laundering millions from DMM bitcoin hack, some funds frozen*. <https://cybernews.com/crypto/lazarus-caught-laundering-millions-from-dmm/>
- [trm-bybit-2025] TRM Labs (2025). *Bybit Hack Update: North Korea Moves to Next Stage of Laundering*. <https://www.trmlabs.com/resources/blog/bybit-hack-update-north-korea-moves-to-next-stage-of-laundering>
- [hackread-bitget-2026] — (2026). *Bitget Confirms $351.6 Million Hack, Suspects North Korea's Lazarus Group*. <https://hackread.com/bitget-hack-suspects-north-korea-lazarus-group/>
