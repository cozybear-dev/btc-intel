"""GraphSense TagPack import/export (https://github.com/graphsense/graphsense-tagpacks)."""

from __future__ import annotations

from typing import Any

import yaml

from btcintel.chain.validate import is_address, normalize_address
from btcintel.labels.store import Tag
from btcintel.labels.taxonomy import Taxonomy

_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def parse_tagpack(text: str, pack: str, taxonomy: Taxonomy) -> tuple[list[Tag], list[str]]:
    doc = yaml.load(text, Loader=_Loader)  # noqa: S506 - safe loader
    if not isinstance(doc, dict) or not isinstance(doc.get("tags"), list):
        raise ValueError(f"{pack}: not a TagPack (missing 'tags' list)")
    header = {k: v for k, v in doc.items() if k != "tags"}
    tags: list[Tag] = []
    warnings: list[str] = []
    for i, raw in enumerate(doc["tags"]):
        if not isinstance(raw, dict):
            warnings.append(f"{pack} tag #{i}: not a mapping")
            continue
        t = {**header, **raw}
        currency = str(t.get("currency") or t.get("network") or "").upper()
        address = str(t.get("address") or "").strip()
        if currency != "BTC" or not address:
            continue
        if not is_address(address):
            warnings.append(f"{pack} tag #{i}: invalid BTC address {address!r}")
            continue
        label, source = t.get("label"), t.get("source")
        if not label or not source:
            warnings.append(f"{pack} tag #{i}: missing label or source")
            continue
        raw_category = t.get("category") or _first(t.get("concepts"))
        category = taxonomy.normalize(raw_category)
        if category is None:
            if raw_category:
                warnings.append(f"{pack} tag #{i}: unknown category {raw_category!r}")
            category = "unknown"
        abuse = taxonomy.normalize(t.get("abuse")) if t.get("abuse") else None
        if t.get("abuse") and abuse is None:
            warnings.append(f"{pack} tag #{i}: unknown abuse {t.get('abuse')!r}")
        tags.append(
            Tag(
                address=normalize_address(address), label=str(label), category=category, abuse=abuse,
                actor=str(t["actor"]) if t.get("actor") else None,
                confidence=str(t.get("confidence") or "unknown"), source=str(source), pack=pack,
                is_cluster_definer=bool(t.get("is_cluster_definer", False)),
                lastmod=str(t["lastmod"]) if t.get("lastmod") else None,
            )
        )
    return tags, warnings


def export_tagpack(tags: list[Tag], title: str, creator: str) -> str:
    entries = []
    for t in tags:
        entry = {
            "address": t.address, "label": t.label, "category": t.category, "abuse": t.abuse,
            "actor": t.actor, "source": t.source, "confidence": t.confidence, "lastmod": t.lastmod,
        }
        entries.append({k: v for k, v in entry.items() if v is not None})
    doc = {"title": title, "creator": creator, "currency": "BTC", "network": "BTC",
           "is_public": False, "tags": entries}
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
