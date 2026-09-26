"""Load the catalog from YAML and cross-check it against itself and docs/kb."""

from __future__ import annotations

import importlib
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from btcintel.catalog.schema import Catalog, Category, Heuristic, Incident, Reference, Technique
from btcintel.chain.validate import is_address, is_txid

LIST_FILES: dict[str, tuple[str, type[BaseModel]]] = {
    "references": ("references.yaml", Reference),
    "categories": ("categories.yaml", Category),
    "heuristics": ("heuristics.yaml", Heuristic),
    "techniques": ("techniques.yaml", Technique),
}


class CatalogError(Exception):
    """A catalog file cannot be parsed or fails schema validation."""


def _read_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise CatalogError(f"{path}: file not found") from e
    except yaml.YAMLError as e:
        raise CatalogError(f"{path}: invalid YAML: {e}") from e


def _validate(model: type[BaseModel], entry: object, where: str) -> BaseModel:
    label = entry.get("id", "?") if isinstance(entry, dict) else "?"
    try:
        return model.model_validate(entry)
    except ValidationError as e:
        raise CatalogError(f"{where} ({label}): {e}") from e


def load_catalog(catalog_dir: Path) -> Catalog:
    parsed: dict[str, list[BaseModel]] = {}
    for key, (filename, model) in LIST_FILES.items():
        path = catalog_dir / filename
        data = _read_yaml(path)
        if data is None:
            data = []
        if not isinstance(data, list):
            raise CatalogError(f"{path}: expected a YAML list of entries, got {type(data).__name__}")
        parsed[key] = [_validate(model, e, f"{filename} entry #{i}") for i, e in enumerate(data)]
    incidents = []
    for path in sorted((catalog_dir / "incidents").glob("*.yaml")):
        data = _read_yaml(path)
        if not isinstance(data, dict):
            raise CatalogError(f"{path}: expected one incident mapping per file")
        incidents.append(_validate(Incident, data, f"incidents/{path.name}"))
    return Catalog(**parsed, incidents=incidents)


def _resolve(dotted: str) -> str | None:
    module_name, _, attr = dotted.rpartition(".")
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        return f"cannot import {module_name}: {e}"
    return None if hasattr(module, attr) else f"{module_name} has no attribute {attr}"


def _check_kb_page(entry_id: str, rel: str, refs: list[str], kb_dir: Path) -> list[str]:
    root = kb_dir.resolve()
    page = (kb_dir / rel).resolve()
    if not page.is_relative_to(root):
        return [f"{entry_id}: kb path {rel!r} escapes docs/kb"]
    if not page.is_file():
        return [f"{entry_id}: kb page {rel} does not exist"]
    text = page.read_text(encoding="utf-8")
    problems = []
    if not text.startswith(f"# {entry_id} "):
        problems.append(f"{entry_id}: {rel} must start with '# {entry_id} — <name>'")
    if "## References" not in text:
        problems.append(f"{entry_id}: {rel} has no '## References' section")
    problems += [f"{entry_id}: {rel} does not cite [{r}]" for r in refs if f"[{r}]" not in text]
    return problems


def check_catalog(cat: Catalog, kb_dir: Path) -> list[str]:
    """Return human-readable consistency problems (empty list = consistent)."""
    problems: list[str] = []
    ref_ids = {r.id for r in cat.references}
    heuristics = {h.id: h for h in cat.heuristics}
    techniques = {t.id: t for t in cat.techniques}

    seen: dict[str, str] = {}
    groups = (
        ("reference", cat.references), ("category", cat.categories),
        ("heuristic", cat.heuristics), ("technique", cat.techniques), ("incident", cat.incidents),
    )
    for kind, entries in groups:
        for e in entries:
            if e.id in seen:
                problems.append(f"duplicate id {e.id} ({seen[e.id]} and {kind})")
            seen[e.id] = kind

    concept_owner: dict[str, str] = {}
    for c in cat.categories:
        for concept in c.gs_concepts:
            if concept in concept_owner:
                problems.append(
                    f"GraphSense concept {concept!r} mapped by both {concept_owner[concept]} and {c.id}"
                )
            concept_owner[concept] = c.id

    def need_refs(owner: str, refs: list[str]) -> None:
        if not refs:
            problems.append(f"{owner}: at least one reference is required")
        problems.extend(f"{owner}: unknown reference {r!r}" for r in refs if r not in ref_ids)

    for h in cat.heuristics:
        need_refs(h.id, h.refs)
        if h.parent is not None:
            parent = heuristics.get(h.parent)
            if parent is None:
                problems.append(f"{h.id}: unknown parent {h.parent}")
            elif parent.parent is not None:
                problems.append(f"{h.id}: parent {h.parent} is itself a child heuristic")
        if h.implemented_by:
            err = _resolve(h.implemented_by)
            if err:
                problems.append(f"{h.id}: implemented_by {h.implemented_by!r}: {err}")

    for t in cat.techniques:
        need_refs(t.id, t.refs)
        problems.extend(
            f"{t.id}: unknown heuristic {hid}" for hid in [*t.evades, *t.detected_by]
            if hid not in heuristics
        )

    for inc in cat.incidents:
        need_refs(inc.id, inc.refs)
        for tid in [*inc.vector, *inc.techniques]:
            if tid not in techniques:
                problems.append(f"{inc.id}: unknown technique {tid}")
        for tid in inc.vector:
            if tid in techniques and techniques[tid].tactic != "acquisition":
                problems.append(f"{inc.id}: vector {tid} is not an acquisition technique")
        for s in inc.seeds:
            if s.ref not in ref_ids:
                problems.append(f"{inc.id}: seed {s.value} cites unknown reference {s.ref!r}")
            valid = is_address(s.value) if s.kind == "address" else is_txid(s.value)
            if not valid:
                problems.append(f"{inc.id}: invalid {s.kind} seed {s.value!r}")

    for entry in [*cat.heuristics, *cat.techniques, *cat.incidents]:
        problems.extend(_check_kb_page(entry.id, entry.kb, entry.refs, kb_dir))
    return problems
