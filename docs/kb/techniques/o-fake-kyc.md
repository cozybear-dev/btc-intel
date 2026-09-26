# O-FAKE-KYC — Fraudulent identities and money mules

> **Tactic:** Integration (cash-out) · **OAK:** OAK-T8.004 · **FATF red-flag areas:** senders_recipients

## Summary

Accounts at on/off-ramps are opened with fictitious or borrowed identities (the Bitfinex launderers used fictitious identities). Off-chain; on-chain detection relies on tags of the deposit addresses involved.

Examples: Bitfinex laundering accounts.

## How it works

The Bitfinex launderers used fictitious identities to set up online accounts, automated transactions with computer programs, and used U.S.-based business accounts to legitimise their banking activity [doj-bitfinex-2022]. FATF red flags include customers providing inconsistent or fictitious information [fatf2020redflags].

## Signals and thresholds

- Off-chain. On chain: deposits into exchange accounts whose deposit addresses tie back to theft flows.

Detected by: —. Evades: —.

## False positives and limitations

—

## Evasion / countermeasures

—

## Detection in btc-intel

btc-intel stops a trace at addresses tagged with a stop category and reports the stop as `labeled`; importing good tags (`btcintel import-tags ...`) is what makes this technique visible.

## Case examples

[I-2016-BITFINEX](../incidents/i-2016-bitfinex.md).

## References

- [doj-bitfinex-2022] U.S. Department of Justice (2022). *Two Arrested for Alleged Conspiracy to Launder $4.5 Billion in Stolen Cryptocurrency*. <https://www.justice.gov/archives/opa/pr/two-arrested-alleged-conspiracy-launder-45-billion-stolen-cryptocurrency>
- [fatf2020redflags] FATF (2020). *Virtual Assets Red Flag Indicators of Money Laundering and Terrorist Financing*. <https://www.fatf-gafi.org/content/dam/fatf-gafi/reports/Virtual-Assets-Red-Flag-Indicators.pdf>
