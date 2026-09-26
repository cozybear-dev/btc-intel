from btcintel.db import open_intel_db
from btcintel.labels.store import CONFIDENCE_LEVELS, Tag, TagStore

A1 = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
BECH = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"


def store() -> TagStore:
    return TagStore(open_intel_db(":memory:"))


def tag(address=A1, label="Binance", pack="p1", **kw) -> Tag:
    return Tag(address=address, label=label, category=kw.pop("category", "exchange"),
               source="https://example.org", pack=pack, confidence=kw.pop("confidence", "authority_data"), **kw)


def test_add_and_lookup_normalises_bech32():
    s = store()
    tag_id = s.add(tag(address=BECH.upper()))
    got = s.for_address(BECH)
    assert len(got) == 1 and got[0].id == tag_id and got[0].address == BECH
    assert got[0].confidence_level == CONFIDENCE_LEVELS["authority_data"] == 60
    assert s.for_address(BECH.upper())[0].id == tag_id


def test_same_address_label_pack_is_replaced():
    s = store()
    s.add(tag(actor="old"))
    s.add(tag(actor="new"))
    got = s.for_address(A1)
    assert len(got) == 1 and got[0].actor == "new"


def test_for_addresses_handles_many():
    s = store()
    s.add_many([tag(address=A1), tag(address=BECH, label="Kraken")])
    many = [A1, BECH] + [f"1Fake{i}" for i in range(1200)]
    got = s.for_addresses(many)
    assert set(got) == {A1, BECH}


def test_search_packs_delete():
    s = store()
    s.add_many([tag(), tag(label="Lazarus Group", pack="ofac", category="individual"), tag(label="Other", pack="p2")])
    assert [t.label for t in s.search("lazarus")] == ["Lazarus Group"]
    assert dict(s.packs()) == {"ofac": 1, "p1": 1, "p2": 1}
    assert s.delete_pack("p2") == 1
    t = s.for_address(A1)[0]
    assert s.delete(t.id) and s.get(t.id) is None


def test_coinbase_rules_longest_first():
    s = store()
    assert s.set_coinbase_rules([("/F2Pool/", "F2Pool"), ("/F2Pool/xyz/", "Other"), ("", "Empty")]) == 2
    assert s.coinbase_rules() == [("/F2Pool/xyz/", "Other"), ("/F2Pool/", "F2Pool")]
