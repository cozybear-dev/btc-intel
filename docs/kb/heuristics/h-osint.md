# H-OSINT — Off-chain attribution

> **Family:** attribution · **Status in btc-intel:** kb_only · **Confidence:** high

## Summary

Most attribution comes from outside the blockchain: sanctions lists, court filings, proof-of-reserves disclosures, ransom notes, forum posts, and interaction (transacting with a service to learn its addresses).

## How it works

- Meiklejohn et al. labelled clusters by transacting with services themselves, then used those labels to interpret flows [meiklejohn2013].
- OFAC's SDN list publishes sanctioned digital-currency addresses; the 2026-09-23 SDN.XML contained 534 XBT (Bitcoin) addresses [ofac-sdn].
- GraphSense TagPacks package attribution tags with source and confidence for sharing [graphsense-tagpacks][haslhofer2021].

## Signals and thresholds

- An address is published by an authority or by the service itself.
- An address is observed while transacting with a service.

## False positives and limitations

- Stale, mistyped or deliberately poisoned reports.
- Tags must carry provenance and confidence.

## Evasion / countermeasures

Services rotating deposit addresses; actors never reusing addresses.

## Detection in btc-intel

btc-intel imports tags from GraphSense TagPacks, the OFAC SDN list, mempool mining-pool data and ransomwhe.re, with their confidence levels, and lets analysts add and export their own tags.

Knowledge-base only: btc-intel does not implement this as an automated detector.

## Case examples

No public case study is attached to this technique yet.

## References

- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
- [ofac-sdn] U.S. Department of the Treasury (2026). *OFAC Specially Designated Nationals (SDN) list, XML export*. <https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML>
- [graphsense-tagpacks] — (2026). *GraphSense public TagPacks*. <https://github.com/graphsense/graphsense-tagpacks>
- [haslhofer2021] Bernhard Haslhofer, Rainer Stütz, Matteo Romiti, Ross King (2021). *GraphSense: A General-Purpose Cryptoasset Analytics Platform*. <https://arxiv.org/abs/2102.13613>
