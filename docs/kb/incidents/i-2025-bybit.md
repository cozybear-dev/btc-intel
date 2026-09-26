# I-2025-BYBIT — Bybit hack (ETH) and conversion to BTC

> **Date:** 2025-02-21 · **Loss:** ~$1.5B in ETH · **Attribution:** confirmed (North Korea's TraderTraitor (Lazarus Group))

## Summary

On 21 February 2025 North Korea's TraderTraitor stole about $1.5B in ETH from Bybit [trm-bybit-2025]. Laundering proceeded at an unprecedented rate, with most of the ETH converted to BTC through THORChain and swap services such as eXch [dlnews-bybit-2025].

## How it works

[O-KEY-COMPROMISE](../techniques/o-key-compromise.md): the attackers subverted the exchange's multisig signing workflow [trm-bybit-2025].

## Laundering timeline

- 21 February 2025: ETH theft [trm-bybit-2025].
- Following ~10 days: ETH swapped to BTC via THORChain ([O-CHAIN-HOP](../techniques/o-chain-hop.md)) and swap services including eXch ([O-INSTANT-SWAP](../techniques/o-instant-swap.md)) [dlnews-bybit-2025].
- BTC dispersed across thousands of addresses ([O-DISPERSAL](../techniques/o-dispersal.md)), followed by further layering and OTC cash-out ([O-OTC-P2P](../techniques/o-otc-p2p.md)) [trm-bybit-2025].

Technique chain: [O-KEY-COMPROMISE](../techniques/o-key-compromise.md) (Key or signing-infrastructure compromise) → [O-CHAIN-HOP](../techniques/o-chain-hop.md) (Cross-chain bridges and swap protocols) → [O-INSTANT-SWAP](../techniques/o-instant-swap.md) (Instant exchangers) → [O-DISPERSAL](../techniques/o-dispersal.md) (Dispersal and structuring) → [O-OTC-P2P](../techniques/o-otc-p2p.md) (OTC brokers, P2P markets and guarantee marketplaces).

## Signals and thresholds

- THORChain outbound transactions whose memo is `OUT:<ETH tx hash>` ([H-XCHAIN](../heuristics/h-xchain.md)); uniform dispersal ([H-MOTIF-FANOUT](../heuristics/h-motif-fanout.md)).

## Detection in btc-intel

Seeds:

No published Bitcoin seeds yet: The theft itself was on Ethereum; the cited analyses do not list Bitcoin addresses in their text. THORChain outbound transactions (memo OUT:<ETH hash>) and published investigator address lists could supply BTC seeds.

No BTC seeds yet. Given an ETH theft hash, look for THORChain outbound Bitcoin transactions with memo `OUT:<hash>` and trace forward from them.

## Case examples

Cross-chain swap protocols can move a billion dollars across chains within days; memos preserve the link between chains.

## References

- [trm-bybit-2025] TRM Labs (2025). *Bybit Hack Update: North Korea Moves to Next Stage of Laundering*. <https://www.trmlabs.com/resources/blog/bybit-hack-update-north-korea-moves-to-next-stage-of-laundering>
- [dlnews-bybit-2025] — (2025). *North Korea laundering $1.5bn Bybit hack at 'unprecedented rate'*. <https://www.dlnews.com/articles/defi/how-north-korea-is-laundering-the-bybit-hack/>
