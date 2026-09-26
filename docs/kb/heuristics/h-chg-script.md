# H-CHG-SCRIPT — Script-type match

> **Family:** change · **Status in btc-intel:** planned · **Confidence:** medium · **Parent:** [H-CHG](h-chg.md)

## Summary

Wallets usually produce change with the same script type as the coins they spend. When exactly one output matches the inputs' script type, it is probably the change.

## How it works

The Bitcoin Wiki gives the pattern: "If a transaction has all inputs and one output of the same address type (e.g. p2pkh), with the remaining output of a different type (p2sh), then ... the different-address-format output (p2sh) is the payment" [bitcoinwiki-privacy]. Möser and Narayanan include address-type signals among the change-detection features they validate [moser2022].

Example: one P2PKH input; outputs of 400,000 sats (P2WPKH) and 599,000 sats (P2PKH). The P2PKH output is likely change.

## Signals and thresholds

- All inputs share one script type T and exactly one output has type T. Weight +1.0 for that output and −0.5 for each other output.

## False positives and limitations

- The payee uses the same address type as the payer (increasingly common as wallets converge on SegWit and Taproot).

## Evasion / countermeasures

Wallets that generate change matching the payee's script type ([O-CHANGE-AVOIDANCE](../techniques/o-change-avoidance.md)).

## Detection in btc-intel

Planned — Plan 2 implements this in `backend/btcintel/heuristics/change.py`.

## Case examples

No public case study is attached to this technique yet.

## References

- [bitcoinwiki-privacy] Bitcoin Wiki contributors (2024). *Privacy*. <https://en.bitcoin.it/wiki/Privacy>
- [moser2022] Malte Möser, Arvind Narayanan (2022). *Resurrecting Address Clustering in Bitcoin*. Financial Cryptography 2022. <https://arxiv.org/abs/2107.05749>
