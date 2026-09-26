# I-2021-COLONIAL — Colonial Pipeline ransomware payment (DarkSide)

> **Date:** 2021-05-08 · **Loss:** ~75 BTC ransom; 63.7 BTC seized by the FBI · **Attribution:** confirmed (DarkSide ransomware-as-a-service affiliate)

## Summary

Colonial Pipeline paid about 75 BTC to the DarkSide ransomware group on 8 May 2021. By reviewing the public ledger, law enforcement tracked the transfers and identified that about 63.7 BTC had reached an address for which the FBI had the private key, and seized it on 7 June 2021 [doj-colonial-2021]. The seized amount was the affiliate's 85% share; 15% went to the DarkSide developers [elliptic-darkside-2021].

## How it works

[O-RANSOM](../techniques/o-ransom.md): ransomware-as-a-service, where the affiliate that deploys the ransomware and the developers split each ransom [elliptic-darkside-2021].

## Laundering timeline

- 8 May 2021: ~75 BTC ransom paid [doj-colonial-2021].
- May 2021: the ransom is split and the affiliate's share moved through hops to `bc1qq2euq8pw950klpjcawuy4uj39ym43hs6cfsegq` ([O-PEEL-CHAIN](../techniques/o-peel-chain.md)) [elliptic-darkside-2021].
- 7 June 2021: ~63.7 BTC seized; a further 5.9 BTC moved from the same address in transaction `280c5f96…6369` [elliptic-darkside-2021].

Technique chain: [O-RANSOM](../techniques/o-ransom.md) (Ransomware extortion payments) → [O-PEEL-CHAIN](../techniques/o-peel-chain.md) (Peel chains).

## Signals and thresholds

- An 85/15 split of a ransom payment ([H-MOTIF-FANOUT](../heuristics/h-motif-fanout.md) is not triggered; look at output shares), short hop chains ([H-PEEL](../heuristics/h-peel.md)).

## Detection in btc-intel

Seeds:

| Kind | Value | Role | Note | Source |
|---|---|---|---|---|
| address | `bc1qq2euq8pw950klpjcawuy4uj39ym43hs6cfsegq` | seizure | Address holding the affiliate's share, named in the seizure affidavit | [elliptic-darkside-2021] |
| tx | `280c5f96397b9502b99703842712b78fda84f1a0faabf826f683448082f46369` | laundering | Additional 5.9 BTC moved from the affiliate address, not mentioned in the affidavit | [elliptic-darkside-2021] |

Trace **backward** from the affiliate address to the ransom payment: `btcintel trace bc1qq2euq8pw950klpjcawuy4uj39ym43hs6cfsegq --backward --hops 4`. Trace forward from the 5.9-BTC transaction to follow the unseized portion.

## Case examples

Ransom proceeds are traceable while they remain on chain; seizure depended on key access, not only on tracing.

## References

- [doj-colonial-2021] U.S. Department of Justice (2021). *Department of Justice Seizes $2.3 Million in Cryptocurrency Paid to the Ransomware Extortionists Darkside*. <https://www.justice.gov/archives/opa/pr/department-justice-seizes-23-million-cryptocurrency-paid-ransomware-extortionists-darkside>
- [elliptic-darkside-2021] Elliptic (2021). *US Authorities Seize DarkSide Ransom*. <https://www.elliptic.co/blog/us-authorities-seize-darkside>
