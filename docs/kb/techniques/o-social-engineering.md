# O-SOCIAL-ENGINEERING — Victim social engineering

> **Tactic:** Acquisition · **OAK:** — · **FATF red-flag areas:** source_of_funds

## Summary

Attackers impersonate support staff to obtain credentials or keys from individual holders, then drain their wallets (the $243M Genesis-creditor theft in 2024, the $330M theft in 2025).

Examples: Genesis creditor theft Aug 2024, elderly holder theft Apr 2025.

## How it works

- **Genesis creditor (August 2024)**: attackers posed as Google support, persuaded the victim to reset two-factor authentication on a Gemini account, used remote-access software, obtained private keys and drained 4,064 BTC (about $243 million) [theblock-genesis-2024].
- **Elderly holder (April 2025)**: 3,520 BTC (about $330 million) was stolen by social engineering, laundered through a peel chain and more than six instant exchanges and swapped into Monero, briefly moving Monero's price up about 50% [cryptoslate-330m-2025].

## Signals and thresholds

- A long-dormant personal wallet suddenly emptied, followed by peel chains ([H-PEEL](../heuristics/h-peel.md)) into instant-exchange deposits.

Detected by: [H-PEEL](../heuristics/h-peel.md). Evades: —.

## False positives and limitations

- Owners legitimately moving old coins.

## Evasion / countermeasures

Out-of-band verification of support contacts; never share seeds or keys; hardware wallets.

## Detection in btc-intel

Trace forward from the theft transaction in peel mode; instant exchangers must be tagged for the trace to stop at them.

## Case examples

[I-2024-GENESIS-CREDITOR](../incidents/i-2024-genesis-creditor.md), [I-2025-SOCIALENG-330M](../incidents/i-2025-socialeng-330m.md).

## References

- [theblock-genesis-2024] — (2024). *Blockchain sleuth ZachXBT alleges three attackers involved in $243 million theft of single Genesis creditor*. <https://www.theblock.co/post/317349/blockchain-sleuth-zachxbt-alleges-three-perps-involved-in-243-million-theft-of-single-genesis-creditor>
- [cryptoslate-330m-2025] — (2025). *ZachXBT tracks $330M Bitcoin stolen in social engineering scam from elderly American*. <https://cryptoslate.com/zachxbt-tracks-330m-bitcoin-stolen-in-social-engineering-scam-from-elderly-american/>
