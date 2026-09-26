# H-CHG — Change-output detection (vote ensemble)

> **Family:** change · **Status in btc-intel:** planned · **Confidence:** medium

## Summary

Most payments return a remainder to the sender. Identifying that change output extends clusters (change belongs to the sender) and lets a tracer follow the sender's remaining funds instead of the payment. No single signal is reliable, so btc-intel combines several independent signals as weighted votes [bitcoinwiki-privacy].

## How it works

Each signal votes for or against an output being change, with a weight in log-odds. For every spendable output the votes are summed and converted to a probability with the logistic function, so an output with no votes sits at 0.5. The output with the unique highest probability is reported as change if that probability is at least 0.6.

| Signal | Page | Vote |
|---|---|---|
| Change back to an input address | [H-CHG-SELF](h-chg-self.md) | +4.0 |
| Only output with the inputs' script type | [H-CHG-SCRIPT](h-chg-script.md) | +1.0 / −0.5 others |
| Only non-round output | [H-CHG-ROUND](h-chg-round.md) | +1.2 / −1.2 round outputs |
| Output smaller than the smallest input | [H-CHG-UNNECESSARY](h-chg-unnecessary.md) | +1.0 |
| Spent by a transaction with the same wallet fingerprint | [H-CHG-FPCONT](h-chg-fpcont.md) | +1.0 / −0.3 |

Worked example: one P2PKH input of 1,000,000 sats pays 400,000 sats to a P2WPKH address and 599,000 sats to a P2PKH address. The script-type signal gives +1.0 to the 599,000 output and −0.5 to the other; the round-number signal gives +1.2 to the 599,000 output (the only ragged value) and −1.2 to the 400,000 output. Scores 2.2 and −1.7 give probabilities 0.90 and 0.15, so the 599,000 output is reported as change.

Meiklejohn et al. introduced change detection for clustering [meiklejohn2013]. Later work built ground-truth sets to validate change heuristics and to detect cluster collapse [moser2022], and used peel chains to validate and expand clusters [kappos2022].

## Signals and thresholds

- Applies to non-coinbase transactions with two to four spendable outputs that are not multi-party CoinJoins.
- Larger output counts are treated as batch payments, where "change" is ill-defined.

## False positives and limitations

- Batch payments and exact-amount spends have no change.
- Privacy-aware wallets match the payee's script type, randomise ordering and avoid round amounts.
- PayJoin puts a receiver input into the transaction and breaks the unnecessary-input signal.
- Validation studies show individual heuristics have non-trivial false-positive rates, which is why a single weak vote never decides [moser2022][kappos2022].

## Evasion / countermeasures

[O-CHANGE-AVOIDANCE](../techniques/o-change-avoidance.md), [O-PAYJOIN](../techniques/o-payjoin.md), [O-COINJOIN](../techniques/o-coinjoin.md).

## Detection in btc-intel

The `H-CHG` detector emits one `change` finding on the chosen output, with every vote and the per-output probabilities as evidence. Clustering never uses change links by default; tracing uses the change output to follow peel chains.

Planned — Plan 2 implements this in `backend/btcintel/heuristics/change.py`.

## Case examples

No public case study is attached to this technique yet.

## References

- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
- [kappos2022] George Kappos, Haaroon Yousaf, Rainer Stütz, Sofia Rollet, Bernhard Haslhofer, Sarah Meiklejohn (2022). *How to Peel a Million: Validating and Expanding Bitcoin Clusters*. USENIX Security 2022. <https://arxiv.org/abs/2205.13882>
- [moser2022] Malte Möser, Arvind Narayanan (2022). *Resurrecting Address Clustering in Bitcoin*. Financial Cryptography 2022. <https://arxiv.org/abs/2107.05749>
