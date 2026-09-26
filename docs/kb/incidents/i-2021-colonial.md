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

**Dogfood traces (2026-09-26).** Run with `--hops 4 --max-calls 300` against mempool.space, with tags imported from mining pools, OFAC, GraphSense and ransomwhe.re. Taint is haircut unless noted.

- Backward from the affiliate address reaches the ransom wallet: `btcintel trace bc1qq2euq8pw950klpjcawuy4uj39ym43hs6cfsegq --backward --hops 4 --max-calls 300` (78 transactions, complete) ends at hop 4 with 63.69 BTC of taint on `15JFh88FcE4WL6qeMLgX5VEAFCbRXjc9fr`. That address received 75.0003 BTC at 2021-05-08 17:12 UTC (`6a798026…24a2`) and sent it on 35 minutes later (`915fb4f0…bd62`), matching the ~75 BTC ransom of 8 May.
- The affiliate address received 69.6042 BTC on 2021-05-28 (`daf38c7b…69d9`). The seizure transaction `943f2d57…cf7a` (2021-06-07 17:45 UTC) moved 63.7 BTC and returned 5.9042 BTC as change to the same address, which `280c5f96…6369` moved out eight minutes later.
- Forward from `280c5f96…` (`btcintel trace 280c5f96397b9502b99703842712b78fda84f1a0faabf826f683448082f46369 --hops 4 --max-calls 300`; 41 transactions, 5,442 addresses because one hop is a large batch) reaches one labeled exit, `bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h` (exchange, "binance reserve wallets BTC", 0.0108 BTC). The largest remainder, 3.77 BTC, sits at `bc1q8y9y3sq25hfnj0mysy0vf9z379ny88nagv0jyr` at hop 4; `--peel` follows the same remainder and records 49 peel-offs.
- An earlier run stopped at `503d74c4…70e9` as a generic CoinJoin; it is a 223-output batch payout, and the corrected [H-CJ-GENERIC](../heuristics/h-cj-generic.md) rule no longer flags it.
- Neither the ransom wallet nor the affiliate address is tagged in the imported sets (including ransomwhe.re).

## Case examples

Ransom proceeds are traceable while they remain on chain; seizure depended on key access, not only on tracing.

## References

- [doj-colonial-2021] U.S. Department of Justice (2021). *Department of Justice Seizes $2.3 Million in Cryptocurrency Paid to the Ransomware Extortionists Darkside*. <https://www.justice.gov/archives/opa/pr/department-justice-seizes-23-million-cryptocurrency-paid-ransomware-extortionists-darkside>
- [elliptic-darkside-2021] Elliptic (2021). *US Authorities Seize DarkSide Ransom*. <https://www.elliptic.co/blog/us-authorities-seize-darkside>
