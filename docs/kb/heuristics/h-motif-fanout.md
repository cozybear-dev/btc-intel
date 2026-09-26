# H-MOTIF-FANOUT — Fan-out / dispersal

> **Family:** pattern · **Status in btc-intel:** implemented · **Confidence:** medium

## Summary

A transaction with few inputs and many outputs. Uniform output values suggest deliberate dispersal or structuring; varied values are typical of service batch payouts.

## How it works

After the February 2025 Bybit theft, the stolen ETH was largely converted to BTC and dispersed across thousands of addresses (about 11,000, per reporting) [trm-bybit-2025]. Dispersal multiplies the number of paths an investigator must follow. Meiklejohn et al. note that services also pay out in structured batches [meiklejohn2013].

## Signals and thresholds

- At least 10 spendable outputs and at most 3 inputs; not a multi-party CoinJoin.
- Coefficient of variation of output values below 0.2 → `dispersal_uniform` (confidence 0.6); otherwise `fan_out` (0.5).

## False positives and limitations

- Exchange withdrawal batches and mining-pool payouts.

## Evasion / countermeasures

Varying amounts and spreading dispersal over many transactions and blocks.

## Detection in btc-intel

Shape test (`fanout_shape`): ≥10 spendable outputs, ≤3 inputs, not coinbase and not a multi-party CoinJoin. The coefficient of variation of output values separates `dispersal_uniform` (cv < 0.2, confidence 0.6) from `fan_out` (confidence 0.5).

Implemented in `backend/btcintel/heuristics/patterns.py` (`fanout_heuristic`).

## Case examples

No public case study is attached to this technique yet.

## References

- [trm-bybit-2025] TRM Labs (2025). *Bybit Hack Update: North Korea Moves to Next Stage of Laundering*. <https://www.trmlabs.com/resources/blog/bybit-hack-update-north-korea-moves-to-next-stage-of-laundering>
- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
