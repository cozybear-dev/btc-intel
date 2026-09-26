# H-CJ-POST — Post-mix demixing

> **Family:** coinjoin · **Status in btc-intel:** planned · **Confidence:** medium

## Summary

CoinJoin privacy is often lost after the mix. Consolidating several mixed outputs, spending toxic change together with mixed coins, reusing addresses and short remix chains all re-link participants. Entropy measures quantify how linkable a multi-party transaction still is.

## How it works

- **Consolidation**: a transaction spending several outputs of one or more CoinJoins re-links them under [H-CIOH](h-cioh.md).
- **Toxic change**: Tx0 or CoinJoin change spent together with mixed outputs.
- **Subset sums**: in CoinJoins with unequal amounts, matching input and output subsets reveals links ("CoinJoin Sudoku") [atlas2014sudoku].
- **Boltzmann**: computes a transaction's entropy (how many input-to-output mappings are possible) and a link-probability matrix between inputs and outputs [laurentmt2017boltzmann].
- Ecosystem-level measurements of remixing and coordinator behaviour are in [popets2026coinjoin].

## Signals and thresholds

- A transaction spending ≥2 CoinJoin outputs.
- A CoinJoin output spent with Tx0 change.
- Subset-sum partitions of inputs and outputs.

## False positives and limitations

- Deliberate consolidation after long remixing still loses privacy, but may be intentional.

## Evasion / countermeasures

Remixing, coin control and never merging mixed coins.

## Detection in btc-intel

Needs CoinJoin-output tracking across transactions and a bounded subset-sum solver.

Planned for a later phase (not part of Plan 2); see the notes above for what it needs.

## Case examples

No public case study is attached to this technique yet.

## References

- [atlas2014sudoku] Kristov Atlas (2014). *CoinJoin Sudoku*. <http://www.coinjoinsudoku.com/>
- [laurentmt2017boltzmann] LaurentMT (2017). *Introducing Boltzmann*. <https://medium.com/@laurentmt/introducing-boltzmann-85930984a159>
- [popets2026coinjoin] — (2026). *CoinJoin ecosystem insights for Wasabi 1.x, Wasabi 2.x and Whirlpool coordinator-based privacy mixers*. PoPETs 2026. <https://petsymposium.org/popets/2026/popets-2026-0061.php>
