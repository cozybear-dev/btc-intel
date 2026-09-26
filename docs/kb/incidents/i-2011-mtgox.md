# I-2011-MTGOX — Mt. Gox hack

> **Date:** 2011-09 · **Loss:** At least ~647,000 BTC stolen from Mt. Gox's wallets (Sep 2011 – May 2014, per DOJ) · **Attribution:** suspected (Alexey Bilyuchenko, Aleksandr Verner and co-conspirators (charged, not convicted))

## Summary

From September 2011 through at least May 2014, attackers with unauthorised access to Mt. Gox's server moved bitcoin from its wallets to addresses they controlled, taking at least about 647,000 BTC, the vast majority of customers' coins. In June 2023 the DOJ charged Russian nationals Alexey Bilyuchenko and Aleksandr Verner with laundering the proceeds [doj-mtgox-2023]. BTC-e, whose operator later pleaded guilty to money-laundering conspiracy, is linked to laundering part of them [doj-btce-2024].

## How it works

Long-running compromise of an exchange's wallet infrastructure ([O-KEY-COMPROMISE](../techniques/o-key-compromise.md)): repeated unauthorised transfers over years rather than one large theft [doj-mtgox-2023].

## Laundering timeline

- 2011–2014: coins drained from Mt. Gox wallets to attacker-controlled addresses [doj-mtgox-2023].
- 2011–2017: proceeds laundered in part through BTC-e, a high-risk exchange ([O-HIGH-RISK-EXCHANGE](../techniques/o-high-risk-exchange.md)) [doj-btce-2024].
- Charges only in 2023: a decade between theft and prosecution ([O-DORMANCY](../techniques/o-dormancy.md)).

Technique chain: [O-KEY-COMPROMISE](../techniques/o-key-compromise.md) (Key or signing-infrastructure compromise) → [O-DORMANCY](../techniques/o-dormancy.md) (Dormancy and delayed laundering) → [O-HIGH-RISK-EXCHANGE](../techniques/o-high-risk-exchange.md) (High-risk exchanges).

## Signals and thresholds

- Slow, repeated outflows from a service's hot wallet; deposits into a high-risk exchange's cluster ([H-CIOH](../heuristics/h-cioh.md), address tags).

## Detection in btc-intel

Seeds:

No published Bitcoin seeds yet: The DOJ releases do not list Bitcoin addresses; the charging documents or the Mt. Gox trustee's reports could supply them.

No seeds yet. Once addresses are added, trace forward with stop categories `exchange` and `high_risk_exchange`.

## Case examples

Theft can be slow and invisible for years; exchange-side compromise is detected by reconciliation, not by the chain alone.

## References

- [doj-mtgox-2023] U.S. Department of Justice (2023). *Russian Nationals Charged With Hacking One Cryptocurrency Exchange and Illicitly Operating Another*. <https://www.justice.gov/archives/opa/pr/russian-nationals-charged-hacking-one-cryptocurrency-exchange-and-illicitly-operating-another>
- [doj-btce-2024] U.S. Department of Justice (2024). *BTC-e Operator Pleads Guilty to Money Laundering Conspiracy*. <https://www.justice.gov/archives/opa/pr/btc-e-operator-pleads-guilty-money-laundering-conspiracy>
