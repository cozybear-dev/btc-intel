import copy
from pathlib import Path

import pytest
import yaml

MINIMAL = {
    "references": [
        {"id": "ref1", "title": "A paper", "authors": ["A. Author"], "year": 2020,
         "kind": "paper", "url": "https://example.org/paper"},
    ],
    "categories": [
        {"id": "exchange", "kind": "entity", "name": "Exchange", "risk": "low",
         "gs_concepts": ["exchange"], "stop_trace": True, "description": "Custodial exchange."},
    ],
    "heuristics": [
        {"id": "H-X", "name": "Example heuristic", "family": "clustering", "status": "planned",
         "confidence": "high", "summary": "s", "signals": ["a"], "refs": ["ref1"],
         "kb": "heuristics/h-x.md"},
    ],
    "techniques": [
        {"id": "O-THEFT", "name": "Theft", "tactic": "acquisition", "summary": "s",
         "refs": ["ref1"], "kb": "techniques/o-theft.md"},
        {"id": "O-Y", "name": "Layering", "tactic": "layering", "summary": "s",
         "detected_by": ["H-X"], "refs": ["ref1"], "kb": "techniques/o-y.md"},
    ],
}
INCIDENT = {
    "id": "I-2020-TEST", "name": "Test incident", "date": "2020-01-02", "loss": "1 BTC", "btc": 1.0,
    "vector": ["O-THEFT"], "attribution": "unknown", "techniques": ["O-Y"], "summary": "s",
    "seeds": [{"kind": "address", "value": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "role": "theft",
               "ref": "ref1"}],
    "refs": ["ref1"], "kb": "incidents/i-2020-test.md",
}


def _write_page(kb_dir: Path, entry: dict) -> None:
    page = kb_dir / entry["kb"]
    page.parent.mkdir(parents=True, exist_ok=True)
    cites = " ".join(f"[{r}]" for r in entry["refs"])
    page.write_text(f"# {entry['id']} — {entry['name']}\n\n## References\n\n{cites}\n")


@pytest.fixture
def make_catalog(tmp_path):
    """Write a minimal valid catalog + KB; `mutate(data, incident)` may edit before writing."""

    def _make(mutate=None):
        data = copy.deepcopy(MINIMAL)
        incident = copy.deepcopy(INCIDENT)
        if mutate:
            mutate(data, incident)
        cat_dir, kb_dir = tmp_path / "catalog", tmp_path / "kb"
        (cat_dir / "incidents").mkdir(parents=True)
        for key, entries in data.items():
            (cat_dir / f"{key}.yaml").write_text(yaml.safe_dump(entries, sort_keys=False))
        (cat_dir / "incidents" / f"{incident['id']}.yaml").write_text(yaml.safe_dump(incident))
        for entry in [*data["heuristics"], *data["techniques"], incident]:
            if not entry["kb"].startswith(".."):
                _write_page(kb_dir, entry)
        return cat_dir, kb_dir

    return _make
