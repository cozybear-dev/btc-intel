# O-PEEL-CHAIN — Peel chains

> **Tactic:** Layering · **OAK:** — · **FATF red-flag areas:** transaction_patterns

## Summary

A large amount is moved through long chains of 1-in/2-out transactions, peeling small amounts to deposits while the remainder moves to fresh addresses.

Examples: Bitfinex 2016 laundering, 2025 $330M theft.

## How it works

```
 10.0 ─► 0.5 peel ─► deposit
      └► 9.49 ─► 0.4 peel ─► deposit
               └► 9.08 ─► ...
```
The Bitcoin Wiki describes a single address starting with a large amount, from which smaller amounts are peeled off repeatedly, "potentially for hundreds or thousands of hops" [bitcoinwiki-privacy]. Meiklejohn et al. followed peel chains from thefts to exchanges [meiklejohn2013]; Kappos et al. built a peel-chain heuristic to validate and expand clusters [kappos2022]. The 2025 $330 million theft was laundered with a peel chain before being swapped to Monero [cryptoslate-330m-2025].

## Signals and thresholds

- Consecutive 1–2-input, 2-output transactions where one output carries ≥75% of the value ([H-PEEL](../heuristics/h-peel.md)); the change detector ([H-CHG](../heuristics/h-chg.md)) picks the remainder.

Detected by: [H-PEEL](../heuristics/h-peel.md), [H-CHG](../heuristics/h-chg.md). Evades: [H-CIOH](../heuristics/h-cioh.md).

## False positives and limitations

- Exchanges' and mining pools' withdrawal patterns look similar [meiklejohn2013].

## Evasion / countermeasures

Splitting into many parallel chains; inserting CoinJoins.

## Detection in btc-intel

Trace with `--peel` (or peel mode in the UI) to follow only the remainder, recording each peel as a `peel_off` stop; `POST /api/peel` walks a single chain.

## Case examples

[I-2016-BITFINEX](../incidents/i-2016-bitfinex.md), [I-2021-COLONIAL](../incidents/i-2021-colonial.md), [I-2025-SOCIALENG-330M](../incidents/i-2025-socialeng-330m.md).

## References

- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
- [kappos2022] George Kappos, Haaroon Yousaf, Rainer Stütz, Sofia Rollet, Bernhard Haslhofer, Sarah Meiklejohn (2022). *How to Peel a Million: Validating and Expanding Bitcoin Clusters*. USENIX Security 2022. <https://arxiv.org/abs/2205.13882>
- [cryptoslate-330m-2025] — (2025). *ZachXBT tracks $330M Bitcoin stolen in social engineering scam from elderly American*. <https://cryptoslate.com/zachxbt-tracks-330m-bitcoin-stolen-in-social-engineering-scam-from-elderly-american/>
