import pytest

from btcintel.catalog.loader import CatalogError, check_catalog, load_catalog


def problems_for(make_catalog, mutate=None):
    cat_dir, kb_dir = make_catalog(mutate)
    return check_catalog(load_catalog(cat_dir), kb_dir)


def test_minimal_catalog_is_clean(make_catalog):
    assert problems_for(make_catalog) == []


def test_lookup_helpers(make_catalog):
    cat_dir, _ = make_catalog()
    cat = load_catalog(cat_dir)
    assert cat.heuristic("H-X").name == "Example heuristic"
    assert cat.category("exchange").risk == "low"
    with pytest.raises(KeyError):
        cat.technique("O-NOPE")


def test_unknown_reference_reported(make_catalog):
    def mutate(data, incident):
        data["heuristics"][0]["refs"] = ["ref1", "nope"]

    assert any("unknown reference 'nope'" in p for p in problems_for(make_catalog, mutate))


def test_duplicate_id_reported(make_catalog):
    def mutate(data, incident):
        data["heuristics"].append(dict(data["heuristics"][0]))

    assert any("duplicate id H-X" in p for p in problems_for(make_catalog, mutate))


def test_technique_unknown_heuristic_reported(make_catalog):
    def mutate(data, incident):
        data["techniques"][1]["evades"] = ["H-MISSING"]

    assert any("unknown heuristic H-MISSING" in p for p in problems_for(make_catalog, mutate))


def test_incident_vector_must_be_acquisition(make_catalog):
    def mutate(data, incident):
        incident["vector"] = ["O-Y"]

    assert any("not an acquisition technique" in p for p in problems_for(make_catalog, mutate))


def test_invalid_seed_reported(make_catalog):
    def mutate(data, incident):
        incident["seeds"][0]["value"] = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb"

    assert any("invalid address seed" in p for p in problems_for(make_catalog, mutate))


def test_seed_with_whitespace_reported(make_catalog):
    def mutate(data, incident):
        incident["seeds"][0]["value"] = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa "

    assert any("invalid address seed" in p for p in problems_for(make_catalog, mutate))


def test_tx_seed_validated(make_catalog):
    def mutate(data, incident):
        incident["seeds"] = [{"kind": "tx", "value": "ab" * 31, "role": "theft", "ref": "ref1"}]

    assert any("invalid tx seed" in p for p in problems_for(make_catalog, mutate))


def test_missing_kb_page_reported(make_catalog):
    cat_dir, kb_dir = make_catalog()
    (kb_dir / "heuristics" / "h-x.md").unlink()
    problems = check_catalog(load_catalog(cat_dir), kb_dir)
    assert any("kb page heuristics/h-x.md does not exist" in p for p in problems)


def test_kb_page_must_cite_every_ref(make_catalog):
    cat_dir, kb_dir = make_catalog()
    (kb_dir / "heuristics" / "h-x.md").write_text("# H-X — Example heuristic\n\n## References\n")
    problems = check_catalog(load_catalog(cat_dir), kb_dir)
    assert any("does not cite [ref1]" in p for p in problems)


def test_kb_page_title_must_start_with_id(make_catalog):
    cat_dir, kb_dir = make_catalog()
    (kb_dir / "heuristics" / "h-x.md").write_text("# Wrong\n\n## References\n[ref1]\n")
    problems = check_catalog(load_catalog(cat_dir), kb_dir)
    assert any("must start with '# H-X" in p for p in problems)


def test_kb_path_escape_rejected(make_catalog):
    def mutate(data, incident):
        data["heuristics"][0]["kb"] = "../outside.md"

    cat_dir, kb_dir = make_catalog(mutate)
    (kb_dir.parent / "outside.md").write_text("# H-X — x\n\n## References\n[ref1]\n")
    problems = check_catalog(load_catalog(cat_dir), kb_dir)
    assert any("escapes docs/kb" in p for p in problems)


def test_duplicate_graphsense_concept_reported(make_catalog):
    def mutate(data, incident):
        data["categories"].append(
            {"id": "exchange2", "kind": "entity", "name": "E2", "risk": "low",
             "gs_concepts": ["exchange"], "description": "d"}
        )

    assert any("concept 'exchange'" in p for p in problems_for(make_catalog, mutate))


def test_child_heuristic_parent_must_exist(make_catalog):
    def mutate(data, incident):
        data["heuristics"][0]["parent"] = "H-NOPE"

    assert any("unknown parent H-NOPE" in p for p in problems_for(make_catalog, mutate))


def test_implemented_by_must_resolve(make_catalog):
    def mutate(data, incident):
        data["heuristics"][0]["status"] = "implemented"
        data["heuristics"][0]["implemented_by"] = "btcintel.nope.missing"

    assert any("cannot import btcintel.nope" in p for p in problems_for(make_catalog, mutate))


def test_implemented_requires_implemented_by(make_catalog):
    def mutate(data, incident):
        data["heuristics"][0]["status"] = "implemented"

    cat_dir, _ = make_catalog(mutate)
    with pytest.raises(CatalogError, match="heuristics.yaml entry #0 \\(H-X\\)"):
        load_catalog(cat_dir)


def test_incident_needs_seeds_or_note(make_catalog):
    def mutate(data, incident):
        incident["seeds"] = []

    cat_dir, _ = make_catalog(mutate)
    with pytest.raises(CatalogError, match="seeds_note"):
        load_catalog(cat_dir)


def test_list_file_must_be_a_list(make_catalog):
    cat_dir, _ = make_catalog()
    (cat_dir / "heuristics.yaml").write_text("id: H-X\nname: oops\n")
    with pytest.raises(CatalogError, match="heuristics.yaml: expected a YAML list"):
        load_catalog(cat_dir)


def test_unknown_field_rejected(make_catalog):
    def mutate(data, incident):
        data["references"][0]["colour"] = "red"

    cat_dir, _ = make_catalog(mutate)
    with pytest.raises(CatalogError, match="references.yaml entry #0 \\(ref1\\)"):
        load_catalog(cat_dir)
