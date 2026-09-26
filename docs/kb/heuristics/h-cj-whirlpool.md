# H-CJ-WHIRLPOOL — Whirlpool mix (Samourai / Ashigaru)

> **Family:** coinjoin · **Status in btc-intel:** planned · **Confidence:** high · **Parent:** [H-CJ](h-cj.md)

## Summary

Whirlpool mixes (Samourai 2019–2024, relaunched by Ashigaru in June 2025) have equal numbers of inputs and outputs, and every output is exactly the pool denomination.

## How it works

```
 5–10 inputs (pool denomination, or denomination + miner fee for fresh premix)
      ─► mix ─► 5–10 outputs of exactly the pool denomination
```
Pool sizes: 100,000, 1,000,000, 5,000,000 and 50,000,000 sats for Samourai's pools, and 2,500,000 and 25,000,000 sats (0.025 and 0.25 BTC) for Ashigaru's coordinator [crocsmuni-coinjoin][ashigaru-whirlpool-2025]. Ashigaru's announcement states a first-mix anonymity set of 5 minimum and 10 maximum when a surge cycle is triggered, and a fixed 5% pool fee [ashigaru-whirlpool-2025]. The DOJ indictment of Samourai's founders describes Whirlpool as coordinating mixing between users [doj-samourai-2024].

## Signals and thresholds

- No OP_RETURN; `n_in == n_out` in [5, 10]; every output equals a pool denomination D; every input is within [D, 1.1·D + 20,000] sats.

## False positives and limitations

- No false positives were observed; the structure is highly specific.

## Evasion / countermeasures

Remixing increases ambiguity; privacy is lost by post-mix consolidation ([H-CJ-POST](h-cj-post.md)).

## Detection in btc-intel

Planned — Plan 2 implements this in `backend/btcintel/heuristics/coinjoin.py`.

## Case examples

No public case study is attached to this technique yet.

## References

- [crocsmuni-coinjoin] CRoCS MUNI (2026). *coinjoin-analysis: processing and analysis of Wasabi 1.x/2.x, Whirlpool and JoinMarket coinjoins (with Dumplings datasets)*. <https://github.com/crocs-muni/coinjoin-analysis>
- [ashigaru-whirlpool-2025] Ashigaru (2025). *Announcement: new Zerolink coinjoin coordinator*. <https://ashigaru.rs/news/announcement-whirlpool/>
- [doj-samourai-2024] U.S. Attorney's Office SDNY (2024). *Founders And CEO Of Cryptocurrency Mixing Service Arrested And Charged With Money Laundering And Unlicensed Money Transmitting Offenses*. <https://www.justice.gov/usao-sdny/pr/founders-and-ceo-cryptocurrency-mixing-service-arrested-and-charged-money-laundering>
