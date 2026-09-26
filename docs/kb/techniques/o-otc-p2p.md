# O-OTC-P2P — OTC brokers, P2P markets and guarantee marketplaces

> **Tactic:** Integration (cash-out) · **OAK:** — · **FATF red-flag areas:** senders_recipients

## Summary

Proceeds are sold for fiat or stablecoins via OTC brokers, P2P venues or guarantee marketplaces such as Huione Guarantee (DMM 2024). Detection relies on address tags.

Examples: Huione Guarantee, Chinese OTC networks, Bisq, HodlHodl.

## How it works

Proceeds are sold for fiat or stablecoins off exchange. DMM Bitcoin proceeds reached the Huione Guarantee marketplace via mixing, bridging and USDT on Tron; about $35 million was moved there in July 2024 [invezz-dmm-huione-2024][cybernews-dmm-2024].

## Signals and thresholds

- Deposits to OTC or P2P-escrow addresses (categories `otc_broker`, `p2p_exchange`).

Detected by: —. Evades: —.

## False positives and limitations

- Legitimate OTC trading.

## Evasion / countermeasures

—

## Detection in btc-intel

btc-intel stops a trace at addresses tagged with a stop category and reports the stop as `labeled`; importing good tags (`btcintel import-tags ...`) is what makes this technique visible.

## Case examples

[I-2024-DMM](../incidents/i-2024-dmm.md), [I-2025-BYBIT](../incidents/i-2025-bybit.md).

## References

- [invezz-dmm-huione-2024] — (2024). *DMM Bitcoin hackers launder funds via the notorious Huione Guarantee marketplace*. <https://invezz.com/news/2024/07/15/dmm-bitcoin-hackers-launder-funds-via-the-notorious-huione-guarantee-marketplace/>
- [cybernews-dmm-2024] — (2024). *Lazarus caught laundering millions from DMM bitcoin hack, some funds frozen*. <https://cybernews.com/crypto/lazarus-caught-laundering-millions-from-dmm/>
