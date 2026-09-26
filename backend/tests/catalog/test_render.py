from btcintel.catalog.loader import load_catalog
from btcintel.catalog.render import HEADER, render_all, render_index, render_ttp_matrix
from btcintel.paths import catalog_dir, kb_dir


def test_index_lists_entries_with_links(make_catalog):
    cat_dir, _ = make_catalog()
    text = render_index(load_catalog(cat_dir))
    assert text.startswith(HEADER)
    assert "| [H-X](heuristics/h-x.md) | Example heuristic | clustering | planned | high |" in text
    assert "| [I-2020-TEST](incidents/i-2020-test.md) | 2020-01-02 | Test incident | 1 BTC | unknown |" in text
    assert "**[ref1]**" in text


def test_matrix_groups_by_tactic_and_links_incidents(make_catalog):
    cat_dir, _ = make_catalog()
    text = render_ttp_matrix(load_catalog(cat_dir))
    acq = text.index("## Acquisition")
    lay = text.index("## Layering")
    assert acq < lay
    assert "| [O-Y](techniques/o-y.md) Layering | H-X | — | I-2020-TEST | — |" in text
    assert "- **I-2020-TEST** Test incident (2020-01-02): O-THEFT → O-Y" in text


def test_render_is_deterministic(make_catalog):
    cat_dir, _ = make_catalog()
    cat = load_catalog(cat_dir)
    assert render_all(cat) == render_all(cat)


def test_generated_docs_up_to_date():
    rendered = render_all(load_catalog(catalog_dir()))
    for name, text in rendered.items():
        on_disk = (kb_dir() / name).read_text(encoding="utf-8")
        assert on_disk == text, f"docs/kb/{name} is stale: run `uv run btcintel catalog render`"
