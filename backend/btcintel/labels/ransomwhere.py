"""ransomwhe.re export → ransomware payment address tags."""

from __future__ import annotations

import json

from btcintel.chain.validate import is_address, normalize_address
from btcintel.labels.store import Tag

RANSOMWHERE_URL = "https://api.ransomwhe.re/export"


def parse_ransomwhere(text: str) -> list[Tag]:
    data = json.loads(text)
    rows = data["result"] if isinstance(data, dict) else data
    tags = []
    for r in rows:
        address = str(r.get("address") or "").strip()
        if r.get("blockchain") != "bitcoin" or not is_address(address):
            continue
        tags.append(Tag(
            address=normalize_address(address), label=str(r.get("family") or "Unknown ransomware"),
            category="perpetrator", abuse="ransomware", confidence="forensic",
            source="https://ransomwhe.re/", pack="ransomwhere",
        ))
    return tags
