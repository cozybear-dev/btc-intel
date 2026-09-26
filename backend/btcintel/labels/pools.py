"""mempool/mining-pools pools-v2.json → pool payout-address tags and coinbase tag rules."""

from __future__ import annotations

import json

from btcintel.chain.validate import is_address, normalize_address
from btcintel.labels.store import Tag

POOLS_URL = "https://raw.githubusercontent.com/mempool/mining-pools/master/pools-v2.json"


def parse_pools(text: str) -> tuple[list[Tag], list[tuple[str, str]]]:
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("pools-v2.json: expected a list of pools")
    tags: list[Tag] = []
    rules: list[tuple[str, str]] = []
    for pool in data:
        name = str(pool["name"])
        for address in pool.get("addresses", []):
            if is_address(address):
                tags.append(Tag(
                    address=normalize_address(address), label=name, category="mining_pool",
                    confidence="trusted_provider", source=pool.get("link") or POOLS_URL,
                    pack="mempool_pools",
                ))
        rules.extend((str(tag), name) for tag in pool.get("tags", []) if tag)
    return tags, rules
