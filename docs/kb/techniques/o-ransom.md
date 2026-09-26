# O-RANSOM — Ransomware extortion payments

> **Tactic:** Acquisition · **OAK:** — · **FATF red-flag areas:** source_of_funds

## Summary

Victims pay ransom to a fresh address; proceeds are split between operator and affiliate and moved on through hops, mixers or high-risk exchanges (Colonial Pipeline 2021).

Examples: Colonial Pipeline / DarkSide 2021.

## How it works

```
 victim ─► ransom address ─► hops ─► operator / affiliate splits ─► mixers, exchanges, swappers
```
Colonial Pipeline paid about 75 BTC to DarkSide. By reviewing the public ledger, law enforcement tracked multiple transfers and found that about 63.7 BTC of the proceeds had reached an address whose private key the FBI held; the funds were seized [doj-colonial-2021]. The crowdsourced ransomwhe.re dataset tracks ransomware payment addresses by family [ransomwhere].

## Signals and thresholds

- Payments to fresh addresses matching a ransom note, then splits consistent with affiliate/operator shares ([H-MOTIF-FANOUT](../heuristics/h-motif-fanout.md)) and hop chains ([H-PEEL](../heuristics/h-peel.md)).

Detected by: [H-MOTIF-FANOUT](../heuristics/h-motif-fanout.md), [H-PEEL](../heuristics/h-peel.md). Evades: —.

## False positives and limitations

- Ordinary payments to fresh addresses.

## Evasion / countermeasures

Sanctions screening of ransom addresses; coordination with law enforcement.

## Detection in btc-intel

`btcintel import-tags ransomwhere` labels known ransomware addresses (abuse `ransomware`, risk severe).

## Case examples

[I-2021-COLONIAL](../incidents/i-2021-colonial.md).

## References

- [doj-colonial-2021] U.S. Department of Justice (2021). *Department of Justice Seizes $2.3 Million in Cryptocurrency Paid to the Ransomware Extortionists Darkside*. <https://www.justice.gov/archives/opa/pr/department-justice-seizes-23-million-cryptocurrency-paid-ransomware-extortionists-darkside>
- [ransomwhere] — (2026). *Ransomwhere: open, crowdsourced ransomware payment tracker*. <https://ransomwhe.re/>
