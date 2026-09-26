# I-2020-LUBIAN — LuBian mining-pool weak-key theft

> **Date:** 2020-12-28 · **Loss:** 127,426 BTC (per Arkham); ~127,271 BTC later forfeited by the U.S. · **Attribution:** unknown

## Summary

On 28 December 2020 more than 90% of the LuBian mining pool's bitcoin (127,426 BTC) was drained; Arkham, which disclosed the theft in August 2025, attributes it to weak private-key generation [arkham-lubian-2025]. LuBian then spent about 1.4 BTC across 1,516 transactions carrying OP_RETURN messages to the recipient addresses, asking for the funds back [arkham-lubian-2025]. In October 2025 the U.S. filed a civil forfeiture action for about 127,271 BTC tied to Chen Zhi and the Prince Group [trm-prince-2025]; Elliptic's analysis traces those coins to the LuBian wallets [elliptic-prince-lubian-2025]. China disputes the U.S. account of how the coins were obtained.

## How it works

[O-WEAK-KEY-SWEEP](../techniques/o-weak-key-sweep.md): keys generated with insufficient entropy can be brute-forced and swept without any access to the victim's systems [arkham-lubian-2025].

## Laundering timeline

- 28 December 2020: 127,426 BTC swept [arkham-lubian-2025].
- 2021–2024: the recovery messages are sent (the two example transactions are dated July 2024 on chain); the coins stay put, last consolidated in July 2024 ([O-DORMANCY](../techniques/o-dormancy.md)) [arkham-lubian-2025].
- August 2025: Arkham discloses the theft [arkham-lubian-2025].
- October 2025: U.S. forfeiture action for ~127,271 BTC [trm-prince-2025][elliptic-prince-lubian-2025].

Technique chain: [O-WEAK-KEY-SWEEP](../techniques/o-weak-key-sweep.md) (Weak key-generation exploitation) → [O-DORMANCY](../techniques/o-dormancy.md) (Dormancy and delayed laundering).

## Signals and thresholds

- A single-day mass sweep of a pool's addresses ([H-MOTIF-SWEEP](../heuristics/h-motif-sweep.md)); OP_RETURN text messages addressed to the sweeper; years of dormancy ([H-TEMPORAL](../heuristics/h-temporal.md)).

## Detection in btc-intel

Seeds:

| Kind | Value | Role | Note | Source |
|---|---|---|---|---|
| tx | `a79b1c8df16030691b0ec16db578579a697e1924ec1ba87b0468cdad5a335286` | other | OP_RETURN recovery message from LuBian to a recipient address of the stolen funds | [arkham-lubian-2025] |
| tx | `2a829c04731474e31af2f28e1aac876642397d847d69134b9156a6080f792dad` | other | Second OP_RETURN recovery message cited by Arkham | [arkham-lubian-2025] |

Open either message transaction to see LuBian's address and the recipient address of the stolen funds: `btcintel tx a79b1c8df16030691b0ec16db578579a697e1924ec1ba87b0468cdad5a335286`, then trace backward from the recipient output.

## Case examples

A theft can hide in plain sight for years; OP_RETURN messages are an out-of-band communication channel worth reading.

## References

- [arkham-lubian-2025] Arkham Intelligence (2025). *Arkham Uncovers $3.5B Heist - the Largest Ever*. <https://info.arkm.com/announcements/arkham-uncovers>
- [trm-prince-2025] TRM Labs (2025). *Operation Prince: Inside the Global Effort That Led to the Largest Forfeiture in US History*. <https://www.trmlabs.com/resources/blog/operation-prince-inside-the-global-effort-that-led-to-the-largest-forfeiture-in-us-history>
- [elliptic-prince-lubian-2025] Elliptic (2025). *$15 billion seized by US originates from Iran/China bitcoin miner "theft"*. <https://www.elliptic.co/insights/15-billion-us-seizure-reveals-prince-groups-connection-to-iran-china-bitcoin-mining-theft/>
