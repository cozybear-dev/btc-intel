# H-CHG-FRESH — One-time (fresh) change address

> **Family:** change · **Status in btc-intel:** planned · **Confidence:** medium · **Parent:** [H-CHG](h-chg.md)

## Summary

Change typically goes to a brand-new address, while a payee's address may have been used before. Meiklejohn et al.'s one-time-change heuristic exploits this [meiklejohn2013].

## How it works

An output whose address first appears in this transaction, while every other output address was already seen earlier, is likely the change.

## Signals and thresholds

- Needs first-seen ordering for every address, i.e. a full local index of the chain.

## False positives and limitations

- Modern wallets give payees fresh invoice addresses too, so both outputs are often fresh and the signal is silent.

## Evasion / countermeasures

Payees using fresh addresses (the default in most wallets today).

## Detection in btc-intel

The whole-chain index of spec Phase 3 will provide the first-seen height of every address.

Planned for a later phase (not part of Plan 2); see the notes above for what it needs.

## Case examples

No public case study is attached to this technique yet.

## References

- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
