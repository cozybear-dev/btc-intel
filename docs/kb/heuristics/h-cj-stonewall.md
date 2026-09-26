# H-CJ-STONEWALL — Stonewall / Stonewall-X2

> **Family:** coinjoin · **Status in btc-intel:** planned · **Confidence:** low · **Parent:** [H-CJ](h-cj.md)

## Summary

Stonewall is a Samourai/Ashigaru transaction type with four outputs, one equal-value pair and two change outputs. It may be built by one party (Stonewall) or two (Stonewall-X2), so an observer cannot safely apply CIOH.

## How it works

```
 inputs (1 or 2 owners) ─► payment  ══ decoy of equal value
                           change A    change B
```
The transaction imitates a two-party mini CoinJoin. Because it can really be two-party, btc-intel suppresses [H-CIOH](h-cioh.md) for it. Samourai's services and their use are described in the DOJ indictment [doj-samourai-2024]; background on CoinJoin-like ambiguity is in [bitcoinwiki-privacy].

## Signals and thresholds

- Exactly four spendable outputs, exactly one equal-value pair, at least two inputs.

## False positives and limitations

- Ordinary four-output transactions that contain two equal payments; confidence is therefore 0.4.

## Evasion / countermeasures

By design this makes a single-party transaction look multi-party.

## Detection in btc-intel

Planned — Plan 2 implements this in `backend/btcintel/heuristics/coinjoin.py`.

## Case examples

No public case study is attached to this technique yet.

## References

- [doj-samourai-2024] U.S. Attorney's Office SDNY (2024). *Founders And CEO Of Cryptocurrency Mixing Service Arrested And Charged With Money Laundering And Unlicensed Money Transmitting Offenses*. <https://www.justice.gov/usao-sdny/pr/founders-and-ceo-cryptocurrency-mixing-service-arrested-and-charged-money-laundering>
- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
