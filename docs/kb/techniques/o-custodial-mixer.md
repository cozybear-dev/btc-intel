# O-CUSTODIAL-MIXER — Custodial mixers / tumblers

> **Tactic:** Obfuscation · **OAK:** OAK-T7.001 · **FATF red-flag areas:** anonymity

## Summary

Deposits are pooled and paid out from unrelated coins after delays (Bitcoin Fog, Helix, ChipMixer, Blender.io, Sinbad, Cryptomixer, the last taken down in Dec 2025). Detection relies on address tags of mixer deposit clusters plus amount/time correlation.

Examples: Bitcoin Fog, Helix, ChipMixer, Blender.io, Sinbad, Cryptomixer.

## How it works

```
 user deposit ─► mixer deposit address ─► (pooled, delayed) ─► payouts from unrelated mixer coins
```
- **Cryptomixer**: taken down in Operation Olympia (24–28 November 2025) by Swiss and German authorities with Europol and Eurojust; it had processed about €1.3 billion in bitcoin since 2016, and more than €25 million was seized [europol-cryptomixer-2025].
- **ChipMixer**: taken down on 15 March 2023; according to the DOJ it processed over $3 billion of unlawful transactions [doj-chipmixer-2023].
- **Blender.io**: the first mixer ever sanctioned by OFAC (6 May 2022), for processing over $20.5 million of Lazarus Group's Ronin-hack proceeds [treasury-blender-2022].
- **Sinbad**: sanctioned on 29 November 2023 as a mixer used by North Korea to launder stolen funds [treasury-sinbad-2023].
- The DFRWS 2025 study shows that a tumbler's supposedly ordinary-looking payouts can be recognised by wallet fingerprints [dfrws2025tumbler]. FATF lists the use of mixing or tumbling services among its red-flag indicators [fatf2020redflags].

## Signals and thresholds

- Deposits to tagged mixer addresses (category `mixing_service`).
- Payouts correlated in amount and time with deposits ([H-CORR](../heuristics/h-corr.md)).
- Fingerprint anomalies in payout transactions ([H-FP](../heuristics/h-fp.md)).

Detected by: [H-CORR](../heuristics/h-corr.md). Evades: —.

## False positives and limitations

- Mixer tags go stale when services rotate addresses.

## Evasion / countermeasures

Random delays, split payouts, variable fees.

## Detection in btc-intel

btc-intel stops a trace at addresses tagged with a stop category and reports the stop as `labeled`; importing good tags (`btcintel import-tags ...`) is what makes this technique visible. GraphSense TagPacks and the OFAC list include mixer addresses (e.g. Blender.io).

## Case examples

—

## References

- [europol-cryptomixer-2025] Europol (2025). *Europol and partners shut down 'Cryptomixer'*. <https://www.europol.europa.eu/media-press/newsroom/news/europol-and-partners-shut-down-cryptomixer>
- [dfrws2025tumbler] — (2025). *Tumbling down the stairs: Exploiting a tumbler's attempt to hide with ordinary-looking transactions using wallet fingerprinting*. Forensic Science International: Digital Investigation 52 (DFRWS EU 2025). <https://www.sciencedirect.com/science/article/pii/S2666281725000083>
- [fatf2020redflags] FATF (2020). *Virtual Assets Red Flag Indicators of Money Laundering and Terrorist Financing*. <https://www.fatf-gafi.org/content/dam/fatf-gafi/reports/Virtual-Assets-Red-Flag-Indicators.pdf>
- [doj-chipmixer-2023] U.S. Department of Justice (2023). *Justice Department Investigation Leads to Takedown of Darknet Cryptocurrency Mixer that Processed Over $3 Billion of Unlawful Transactions*. <https://www.justice.gov/archives/opa/pr/justice-department-investigation-leads-takedown-darknet-cryptocurrency-mixer-processed-over-3>
- [treasury-blender-2022] U.S. Department of the Treasury (2022). *U.S. Treasury Issues First-Ever Sanctions on a Virtual Currency Mixer, Targets DPRK Cyber Threats*. <https://home.treasury.gov/news/press-releases/jy0768>
- [treasury-sinbad-2023] U.S. Department of the Treasury (2023). *Treasury Sanctions Mixer Used by the DPRK to Launder Stolen Virtual Currency*. <https://home.treasury.gov/news/press-releases/jy1933>
