from btcintel.catalog.loader import load_catalog
from btcintel.heuristics.base import registry
from btcintel.paths import catalog_dir


def test_registry_matches_catalog_implemented_heuristics():
    cat = load_catalog(catalog_dir())
    implemented = {
        h.id for h in cat.heuristics
        if h.status == "implemented" and h.parent is None and h.family != "taint"
    }
    assert set(registry()) == implemented
