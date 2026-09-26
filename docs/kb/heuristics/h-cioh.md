# H-CIOH — Common-input-ownership

> **Family:** clustering · **Status in btc-intel:** implemented · **Confidence:** high

## Summary

The common-input-ownership heuristic (CIOH) assumes that every input of a transaction is controlled by the same entity. Applied across the whole ledger, and closed transitively (if A co-spends with B and B with C, then A, B and C belong together), it groups addresses into clusters that approximate wallets or entities. It is the cornerstone of address clustering [meiklejohn2013].

## How it works

Every input must be authorised by the key that controls it, and an ordinary wallet builds a payment from its own unspent outputs. Nakamoto anticipated the consequence in the whitepaper's privacy section: "some linking is still unavoidable with multi-input transactions, which necessarily reveal that their inputs were owned by the same owner" [nakamoto2008].

Reid and Harrigan used co-spending to merge public keys into users when building their transaction and user networks [reid2011]. Meiklejohn et al. combined the heuristic with a change-address heuristic to cluster the ledger, label clusters by transacting with known services, and follow flows from services such as Silk Road to exchanges [meiklejohn2013]. Androulaki et al. evaluated how well multi-input and change heuristics profile users when ground truth is known [androulaki2013].

```
 inputs                       outputs
 addr A ──┐                ┌── payee
 addr B ──┼──► transaction ┤
 addr C ──┘                └── change
 ⇒ cluster {A, B, C}
```

## Signals and thresholds

- The transaction spends two or more distinct input addresses.
- The transaction is **not** a CoinJoin, PayJoin or other collaborative construction (see [H-CJ](h-cj.md)).
- Clusters are maintained with a union-find structure; every union is recorded with the transaction that justified it.

## False positives and limitations

- **CoinJoin and PayJoin** deliberately combine inputs from several owners. The Bitcoin Wiki notes that "one of the purposes of CoinJoin is to break this heuristic. Nonetheless this heuristic is very commonly true and it is widely used by transaction surveillance companies" [bitcoinwiki-privacy].
- **Custodial services** co-spend deposits of many customers: the resulting cluster is one *controller* (the service), not one beneficial owner.
- **Cluster collapse**: a single wrong link can merge two large clusters. This is why btc-intel records the evidence for every union and flags clusters whose tags name different entities.

## Evasion / countermeasures

CoinJoin ([O-COINJOIN](../techniques/o-coinjoin.md)), PayJoin and Stonewall-style transactions ([O-PAYJOIN](../techniques/o-payjoin.md)), and simply never spending coins from different sources together (coin control).

## Detection in btc-intel

btc-intel emits a `common_input` finding (confidence 0.95) listing the input addresses, or a `cioh_suppressed` finding when [H-CJ](h-cj.md) classifies the transaction as a multi-party CoinJoin or Stonewall. Whirlpool Tx0 transactions keep CIOH because a Tx0 is built by a single wallet. Cluster expansion (`backend/btcintel/cluster/expand.py`) applies the same rule.

Implemented in `backend/btcintel/heuristics/cioh.py` (`cioh_heuristic`).

## Case examples

Meiklejohn et al. used CIOH-based clusters, labelled by transacting with services, to follow bitcoins from Silk Road to exchanges [meiklejohn2013].

## References

- [nakamoto2008] Satoshi Nakamoto (2008). *Bitcoin: A Peer-to-Peer Electronic Cash System*. <https://bitcoin.org/bitcoin.pdf>
- [reid2011] Fergal Reid, Martin Harrigan (2011). *An Analysis of Anonymity in the Bitcoin System*. <https://arxiv.org/abs/1107.4524>
- [meiklejohn2013] Sarah Meiklejohn, Marjori Pomarole, Grant Jordan, Kirill Levchenko, Damon McCoy, Geoffrey M. Voelker, Stefan Savage (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names*. IMC 2013. <https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf>
- [androulaki2013] Elli Androulaki, Ghassan Karame, Marc Roeschlin, Tobias Scherer, Srdjan Capkun (2013). *Evaluating User Privacy in Bitcoin*. Financial Cryptography 2013. <https://eprint.iacr.org/2012/596>
