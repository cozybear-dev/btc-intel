# H-CJ-WHIRLPOOL-TX0 — Whirlpool Tx0 (premix)

> **Family:** coinjoin · **Status in btc-intel:** implemented · **Confidence:** high · **Parent:** [H-CJ](h-cj.md)

## Summary

A Tx0 prepares coins for Whirlpool: one wallet splits its funds into equal "premix" outputs slightly above a pool denomination, pays the coordinator fee, commits to fee data in an OP_RETURN, and keeps the remainder as unmixed ("toxic") change.

## How it works

```
 wallet UTXOs ─► Tx0 ─┬─ OP_RETURN (binary payload)
                      ├─ coordinator fee
                      ├─ premix × k  (pool denomination + miner-fee allowance)
                      └─ toxic change (unmixed)
```
Tx0s sampled from the Dumplings data carried a 64- or 81-byte binary OP_RETURN, a coordinator fee of 5% of the pool (5,000 sats for the 100k pool, 50,000 for the 1M pool) and only P2WPKH outputs [crocsmuni-coinjoin]. Ashigaru allows up to 20 premix outputs per Tx0. Unlike a mix, a Tx0 is built by one wallet, so [H-CIOH](h-cioh.md) still applies [doj-samourai-2024].

## Signals and thresholds

- Exactly one OP_RETURN, whose payload is at least 40 bytes and is not printable ASCII (THORChain memos are ASCII).
- Every spendable output is P2WPKH.
- For some pool D, the outputs in (D, 1.1·D + 20,000] sats all share one value.

## False positives and limitations

- The Dumplings Tx0 list itself contains some non-Tx0 transactions; btc-intel's regression fixtures keep only entries with exactly one OP_RETURN.

## Evasion / countermeasures

Spending toxic change together with mixed outputs re-links them ([H-CJ-POST](h-cj-post.md)).

## Detection in btc-intel

Implemented in `backend/btcintel/heuristics/coinjoin.py` (`classify_coinjoin`).

## Case examples

No public case study is attached to this technique yet.

## References

- [crocsmuni-coinjoin] CRoCS MUNI (2026). *coinjoin-analysis: processing and analysis of Wasabi 1.x/2.x, Whirlpool and JoinMarket coinjoins (with Dumplings datasets)*. <https://github.com/crocs-muni/coinjoin-analysis>
- [doj-samourai-2024] U.S. Attorney's Office SDNY (2024). *Founders And CEO Of Cryptocurrency Mixing Service Arrested And Charged With Money Laundering And Unlicensed Money Transmitting Offenses*. <https://www.justice.gov/usao-sdny/pr/founders-and-ceo-cryptocurrency-mixing-service-arrested-and-charged-money-laundering>
