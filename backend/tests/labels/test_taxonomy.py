from btcintel.catalog.loader import load_catalog
from btcintel.labels.store import Tag
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir


def tax() -> Taxonomy:
    return Taxonomy.from_catalog(load_catalog(catalog_dir()))


def test_normalize_graphsense_and_own_ids():
    t = tax()
    assert t.normalize("exchange") == "exchange"
    assert t.normalize("Mixing_Service") == "mixing_service"
    assert t.normalize("sanction") == "sanctioned"
    assert t.normalize("service_hack") == "theft"
    assert t.normalize("high_risk_exchange") == "high_risk_exchange"
    assert t.normalize("nonsense") is None and t.normalize(None) is None


def test_risk_levels():
    t = tax()
    assert t.risk("sanctioned") == "severe" and t.risk("exchange") == "low" and t.risk(None) == "none"
    tag = Tag(address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", label="x", category="exchange",
              abuse="sanctioned", source="s", pack="p")
    assert t.risk_of_tag(tag) == "severe"


def test_default_stop_categories():
    stops = tax().default_stop_categories()
    assert {"exchange", "mixing_service", "instant_exchange", "bridge"} <= stops
    assert "individual" not in stops and "sanctioned" not in stops
