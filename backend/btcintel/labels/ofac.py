"""OFAC SDN list (SDN.XML) → sanctioned Bitcoin address tags."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from btcintel.chain.validate import is_address, normalize_address
from btcintel.labels.store import Tag

OFAC_SDN_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML"
XBT = "Digital Currency Address - XBT"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(elem: ET.Element, name: str) -> str | None:
    for child in elem:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return None


def _iso(date: str) -> str | None:
    try:
        return datetime.strptime(date, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def parse_sdn_xml(source: BinaryIO | str | Path) -> tuple[list[Tag], str | None]:
    tags: list[Tag] = []
    published: str | None = None
    for _, elem in ET.iterparse(source, events=("end",)):
        name = _local(elem.tag)
        if name == "Publish_Date":
            published = _iso((elem.text or "").strip())
        elif name == "sdnEntry":
            label = " ".join(filter(None, [_child_text(elem, "firstName"), _child_text(elem, "lastName")]))
            category = "individual" if _child_text(elem, "sdnType") == "Individual" else "organization"
            uid = _child_text(elem, "uid")
            for id_el in (e for e in elem.iter() if _local(e.tag) == "id"):
                address = (_child_text(id_el, "idNumber") or "").strip()
                if _child_text(id_el, "idType") == XBT and is_address(address):
                    tags.append(Tag(
                        address=normalize_address(address), label=label or "OFAC SDN entry",
                        category=category, abuse="sanctioned", confidence="authority_data",
                        source=f"{OFAC_SDN_URL}#uid={uid}", pack="ofac_sdn", lastmod=published,
                    ))
            elem.clear()
    return tags, published
