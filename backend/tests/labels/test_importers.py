import io
import json
import tarfile

import pytest

from btcintel.catalog.loader import load_catalog
from btcintel.db import open_intel_db
from btcintel.labels.importers import (
    import_graphsense_tarball,
    import_ofac,
    import_pools,
    import_ransomwhere,
    import_tagpack_text,
)
from btcintel.labels.ofac import parse_sdn_xml
from btcintel.labels.pools import parse_pools
from btcintel.labels.ransomwhere import parse_ransomwhere
from btcintel.labels.store import TagStore
from btcintel.labels.tagpack import export_tagpack, parse_tagpack
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir

TAX = Taxonomy.from_catalog(load_catalog(catalog_dir()))
BLENDER_1 = "3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4"
BLENDER_2 = "32fbAZMTaQxNd2fAue1PgsiPgWfcsHBQQt"

TAGPACK = f"""
title: Blender.io
creator: GraphSense Core Team
confidence: authority_data
category: mixing_service
currency: BTC
label: Blender.io
source: https://home.treasury.gov/policy-issues/financial-sanctions/recent-actions/20220506
actor: blenderio
tags:
- address: {BLENDER_1}
- address: {BLENDER_2}
  label: Blender.io hot wallet
  abuse: sanction
- address: 0x252a8bd2319d8a555b872990601221b3a2053bce
  currency: ETH
- address: 1NotARealAddressxxxxxxxxxxxxxxxx
- address: bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6
  category: something_new
"""


def test_parse_tagpack_defaults_overrides_and_filters():
    tags, warnings = parse_tagpack(TAGPACK, "gs:blender_io", TAX)
    by_addr = {t.address: t for t in tags}
    assert set(by_addr) == {BLENDER_1, BLENDER_2, "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"}
    t1 = by_addr[BLENDER_1]
    assert (t1.label, t1.category, t1.actor, t1.confidence, t1.pack) == (
        "Blender.io", "mixing_service", "blenderio", "authority_data", "gs:blender_io",
    )
    t2 = by_addr[BLENDER_2]
    assert t2.label == "Blender.io hot wallet" and t2.abuse == "sanctioned"
    assert by_addr["bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"].category == "unknown"
    assert any("invalid BTC address" in w for w in warnings)
    assert any("something_new" in w for w in warnings)


def test_parse_tagpack_rejects_non_tagpack():
    with pytest.raises(ValueError, match="not a TagPack"):
        parse_tagpack("just: a mapping\n", "x", TAX)


def test_export_roundtrip():
    tags, _ = parse_tagpack(TAGPACK, "gs:blender_io", TAX)
    text = export_tagpack(tags, title="t", creator="c")
    again, warnings = parse_tagpack(text, "roundtrip", TAX)
    assert {(t.address, t.label, t.category, t.abuse) for t in again} == {
        (t.address, t.label, t.category, t.abuse) for t in tags
    }
    assert warnings == []


SDN = b"""<?xml version="1.0" standalone="yes"?>
<sdnList xmlns="https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML">
  <publshInformation><Publish_Date>09/23/2026</Publish_Date><Record_Count>2</Record_Count></publshInformation>
  <sdnEntry>
    <uid>24003</uid><firstName>Behzad</firstName><lastName>MESRI</lastName><sdnType>Individual</sdnType>
    <programList><program>CYBER2</program></programList>
    <idList>
      <id><uid>1</uid><idType>Digital Currency Address - XBT</idType><idNumber>12aNKp2iDKuhEde2YfPdd4DFGenRUTKupL</idNumber></id>
      <id><uid>2</uid><idType>Digital Currency Address - ETH</idType><idNumber>0x252a8bd2319d8a555b872990601221b3a2053bce</idNumber></id>
      <id><uid>3</uid><idType>Digital Currency Address - XBT</idType><idNumber>not-an-address</idNumber></id>
    </idList>
  </sdnEntry>
  <sdnEntry>
    <uid>99</uid><lastName>BLENDER.IO</lastName><sdnType>Entity</sdnType>
    <idList><id><uid>4</uid><idType>Digital Currency Address - XBT</idType><idNumber>3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4</idNumber></id></idList>
  </sdnEntry>
</sdnList>"""


def test_parse_sdn_xml():
    tags, published = parse_sdn_xml(io.BytesIO(SDN))
    assert published == "2026-09-23"
    assert [(t.address, t.label, t.category, t.abuse) for t in tags] == [
        ("12aNKp2iDKuhEde2YfPdd4DFGenRUTKupL", "Behzad MESRI", "individual", "sanctioned"),
        ("3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4", "BLENDER.IO", "organization", "sanctioned"),
    ]
    assert all(t.confidence == "authority_data" and t.pack == "ofac_sdn" for t in tags)
    assert tags[0].source.endswith("#uid=24003")


POOLS = json.dumps([
    {"id": 1, "name": "BlockFills", "addresses": ["1PzVut5X6Nx7Mv4JHHKPtVM9Jr9LJ4Rbry"],
     "tags": ["/BlockfillsPool/"], "link": "https://www.blockfills.com/mining"},
    {"id": 2, "name": "ViaBTC", "addresses": [], "tags": ["/ViaBTC/", "viabtc.com deploy"], "link": ""},
])


def test_parse_pools():
    tags, rules = parse_pools(POOLS)
    assert [(t.address, t.label, t.category) for t in tags] == [
        ("1PzVut5X6Nx7Mv4JHHKPtVM9Jr9LJ4Rbry", "BlockFills", "mining_pool")
    ]
    assert ("/ViaBTC/", "ViaBTC") in rules and len(rules) == 3


RANSOM = json.dumps({"result": [
    {"address": "17TMc2UkVRSga2yYvuxSD9Q1XyB2EPRjTF", "blockchain": "bitcoin", "family": "Netwalker (Mailto)"},
    {"address": "0xabc", "blockchain": "ethereum", "family": "X"},
]})


def test_parse_ransomwhere():
    (t,) = parse_ransomwhere(RANSOM)
    assert (t.address, t.label, t.category, t.abuse, t.pack) == (
        "17TMc2UkVRSga2yYvuxSD9Q1XyB2EPRjTF", "Netwalker (Mailto)", "perpetrator", "ransomware", "ransomwhere",
    )


def _tarball(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_import_functions_store_tags():
    store = TagStore(open_intel_db(":memory:"))
    rep = import_tagpack_text(store, TAX, TAGPACK, "gs:blender_io")
    assert rep.tags == 3 and rep.packs == 1
    data = _tarball({
        "graphsense-tagpacks-master/packs/blender_io.yaml": TAGPACK,
        "graphsense-tagpacks-master/packs/eth_only.yaml": "title: e\ncreator: c\ncurrency: ETH\nlabel: x\nsource: s\ntags:\n- address: '0xabc'\n",
        "graphsense-tagpacks-master/packs/broken.yaml": "tags: [unclosed\n",
        "graphsense-tagpacks-master/README.md": "not a pack",
    })
    rep = import_graphsense_tarball(store, TAX, data)
    assert rep.packs == 3 and rep.tags == 3 and len(rep.errors) == 1
    assert import_ofac(store, SDN).tags == 2
    rep = import_pools(store, POOLS.encode())
    assert rep.tags == 1 and store.coinbase_rules()[0][1] in {"ViaBTC", "BlockFills"}
    assert import_ransomwhere(store, RANSOM.encode()).tags == 1
    assert {p for p, _ in store.packs()} == {"gs:blender_io", "ofac_sdn", "mempool_pools", "ransomwhere"}
