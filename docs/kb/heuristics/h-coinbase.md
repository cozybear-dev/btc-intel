# H-COINBASE — Miner attribution

> **Family:** attribution · **Status in btc-intel:** implemented · **Confidence:** high

## Summary

Coinbase transactions create new coins. Pools mark them with tags in the coinbase scriptSig (for example `/ViaBTC/`) and pay known payout addresses, so newly minted coins can be attributed to a pool.

## How it works

mempool.space's curated `mining-pools` data lists, for each pool, its coinbase tags and payout addresses [mempool-mining-pools]. The coinbase of block 900000 contains the text `/ViaBTC/Mined by ndv1/`.

## Signals and thresholds

- The coinbase scriptSig contains a known pool tag (the longest matching tag wins).
- The coinbase pays a known pool address.

## False positives and limitations

- Pools that do not tag, share infrastructure or reuse another pool's tag.

## Evasion / countermeasures

Omitting tags.

## Detection in btc-intel

Findings `miner:<pool>` (confidence 0.9) or `miner:unknown` with the printable coinbase text. Tags and addresses are imported with `btcintel import-tags pools`.

Pool rules are (tag, pool) pairs matched in order against the decoded coinbase scriptSig; the first match wins.

Implemented in `backend/btcintel/heuristics/coinbase.py` (`coinbase_heuristic`).

## Case examples

No public case study is attached to this technique yet.

## References

- [mempool-mining-pools] — (2026). *mempool/mining-pools: mining pool coinbase tags and addresses*. <https://github.com/mempool/mining-pools>
