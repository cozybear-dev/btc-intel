from btcintel.catalog.loader import load_catalog
from btcintel.paths import catalog_dir

EXPECTED = {
    "I-2011-MTGOX", "I-2012-SILKROAD", "I-2016-BITFINEX", "I-2020-LUBIAN", "I-2021-COLONIAL",
    "I-2023-MILKSAD", "I-2024-DMM", "I-2024-GENESIS-CREDITOR", "I-2025-BYBIT",
    "I-2025-SOCIALENG-330M", "I-2026-COLDCARD", "I-2026-LIQUID", "I-2026-BITGET",
}


def test_incident_set():
    assert {i.id for i in load_catalog(catalog_dir()).incidents} == EXPECTED


def test_file_name_matches_id():
    for path in (catalog_dir() / "incidents").glob("*.yaml"):
        assert path.stem in EXPECTED, path.name


def test_most_incidents_have_seeds():
    """Seeds make incidents usable as tracing starting points and regression fixtures."""
    with_seeds = [i.id for i in load_catalog(catalog_dir()).incidents if i.seeds]
    assert len(with_seeds) >= 6, with_seeds
