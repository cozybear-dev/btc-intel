from btcintel.catalog.loader import check_catalog, load_catalog
from btcintel.paths import catalog_dir, kb_dir


def test_repository_catalog_is_consistent():
    problems = check_catalog(load_catalog(catalog_dir()), kb_dir())
    assert problems == [], "\n".join(problems)
