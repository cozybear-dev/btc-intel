# H-TAINT — Taint analysis models

> **Family:** taint · **Status in btc-intel:** implemented · **Confidence:** medium

## Summary

Taint analysis decides how much of each output of a transaction derives from tainted (for example stolen) inputs. The model chosen changes the answer dramatically.

## How it works

- **Poison** "classifies all of the transaction outputs as tainted outputs in the transactions with any tainted input, regardless of the number of tainted Bitcoins involved" [tironsakkul2019]; Möser, Böhme and Breuker discuss poison and haircut policies for risk scoring [moser2014risk].
- **Haircut** distributes taint to every output in proportion to value.
- **FIFO** follows the UK precedent of Clayton's case: "the first penny into an account goes to satisfy the first withdrawal". Anderson et al. propose applying it to the ordered inputs and outputs of Bitcoin transactions [anderson2018].
- Tironsakkul et al. propose **LIFO** and **TIHO** (taint in, highest out) and compare all methods on real thefts [tironsakkul2019].

Worked example: inputs of 60,000 and 40,000 sats, where only the 40,000-sat input is tainted; outputs of 70,000 and 29,000 sats; fee 1,000.

| Model | Output 0 (70,000) | Output 1 (29,000) |
|---|---|---|
| Poison | 70,000 | 29,000 |
| Haircut | 28,000 | 11,600 |
| FIFO | 10,000 | 29,000 |

Under FIFO the tainted input occupies positions 60,000–100,000 of the input stream. Output 0 covers 0–70,000 (10,000 tainted), output 1 covers 70,000–99,000 (29,000 tainted), and the last 1,000 goes to the fee.

## Signals and thresholds

- Not a detector, but a flow model used by tracing and exposure scoring.

## False positives and limitations

- Poison vastly over-taints; haircut dilutes taint into every downstream coin; FIFO depends on the arbitrary ordering of inputs and outputs.

## Evasion / countermeasures

Mixing with clean coins dilutes haircut taint; ordering tricks affect FIFO.

## Detection in btc-intel

Poison, haircut and FIFO are implemented forward (where funds went) and backward (where funds came from). Haircut and FIFO never create or lose taint beyond the transaction's value (property-tested).

Worked example (inputs 60,000 + 40,000 sats, where input 1 is tainted; outputs 70,000 + 29,000 sats; fee 1,000):

| Model | Output 0 | Output 1 |
|---|---|---|
| haircut | 28,000 | 11,600 |
| FIFO | 10,000 | 29,000 |
| poison | 70,000 | 29,000 |

Taint amounts are clamped to `[0, value]`. FIFO treats the tainted sats as the first sats of each input (forward) or output (backward) and maps positions in the input value stream onto the output stream, with the fee at the end of the output stream. Poison taints every positive-value output fully.

Implemented in `backend/btcintel/trace/taint.py` (`forward`).

## Case examples

No public case study is attached to this technique yet.

## References

- [anderson2018] Ross Anderson, Ilia Shumailov, Mansoor Ahmed, Alessandro Rietmann (2018). *Bitcoin Redux*. WEIS 2018. <https://www.cl.cam.ac.uk/~rja14/Papers/bitcoin-redux.pdf>
- [tironsakkul2019] Tin Tironsakkul, Manuel Maarek, Andrea Eross, Mike Just (2019). *Probing the Mystery of Cryptocurrency Theft: An Investigation into Methods for Taint Analysis*. <https://arxiv.org/abs/1906.05754>
- [moser2014risk] Malte Möser, Rainer Böhme, Dominic Breuker (2014). *Towards Risk Scoring of Bitcoin Transactions*. Financial Cryptography 2014 Workshops. <https://link.springer.com/chapter/10.1007/978-3-662-44774-1_2>
