import pytest

from btcintel.catalog.loader import load_catalog
from btcintel.catalog.online import check_urls, verify_seeds
from btcintel.paths import catalog_dir

pytestmark = pytest.mark.network


def test_reference_urls_resolve():
    cat = load_catalog(catalog_dir())
    # some publishers (e.g. sciencedirect) return 403 to scripts; those are reviewed manually
    problems = [p for p in check_urls(r.url for r in cat.references) if p[1] != "HTTP 403"]
    assert problems == []


def test_incident_seeds_exist_on_chain():
    assert verify_seeds(load_catalog(catalog_dir())) == []
