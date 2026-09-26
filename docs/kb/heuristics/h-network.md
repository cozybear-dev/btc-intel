# H-NETWORK — Network-layer deanonymisation

> **Family:** network · **Status in btc-intel:** kb_only · **Confidence:** medium

## Summary

Observing which peer first relays a transaction can reveal the originating IP address. This is out of scope for on-chain analysis but relevant to overall privacy.

## How it works

- Biryukov, Khovratovich and Pustogarov showed that clients' IP addresses can be linked to their transactions by exploiting how the P2P network forwards them [biryukov2014].
- Koshy, Koshy and McDaniel analysed relay patterns in live P2P traffic to map transactions to IP addresses [koshy2014].
- Dandelion++ proposes relaying transactions along a random path before broadcasting them, which limits these attacks [fanti2018].

## Signals and thresholds

- First-relay peer statistics across many listening nodes.

## False positives and limitations

- Tor/VPN usage and third-party broadcast services.

## Evasion / countermeasures

Broadcasting over Tor, through third-party services, or with Dandelion-style relay.

## Detection in btc-intel

Out of scope: btc-intel analyses only on-chain data.

Knowledge-base only: btc-intel does not implement this as an automated detector.

## Case examples

No public case study is attached to this technique yet.

## References

- [biryukov2014] Alex Biryukov, Dmitry Khovratovich, Ivan Pustogarov (2014). *Deanonymisation of clients in Bitcoin P2P network*. ACM CCS 2014. <https://arxiv.org/abs/1405.7418>
- [koshy2014] Philip Koshy, Diana Koshy, Patrick McDaniel (2014). *An Analysis of Anonymity in Bitcoin Using P2P Network Traffic*. Financial Cryptography 2014. <https://link.springer.com/chapter/10.1007/978-3-662-45472-5_30>
- [fanti2018] Giulia Fanti, Shaileshh Bojja Venkatakrishnan, Surya Bakshi, Bradley Denby, Shruti Bhargava, Andrew Miller, Pramod Viswanath (2018). *Dandelion++: Lightweight Cryptocurrency Networking with Formal Anonymity Guarantees*. <https://arxiv.org/abs/1805.11060>
