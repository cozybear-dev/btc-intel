from btcintel.catalog.loader import load_catalog
from btcintel.paths import catalog_dir

EXPECTED = {
    "H-CIOH", "H-REUSE", "H-PUBKEY", "H-CHG", "H-CHG-SELF", "H-CHG-SCRIPT", "H-CHG-ROUND",
    "H-CHG-UNNECESSARY", "H-CHG-FPCONT", "H-CHG-FRESH", "H-CHG-POSITION", "H-FP", "H-CJ",
    "H-CJ-WASABI1", "H-CJ-WASABI2", "H-CJ-WHIRLPOOL", "H-CJ-WHIRLPOOL-TX0", "H-CJ-JOINMARKET",
    "H-CJ-STONEWALL", "H-CJ-GENERIC", "H-CJ-POST", "H-PEEL", "H-MOTIF-FANOUT", "H-MOTIF-FANIN",
    "H-MOTIF-SWEEP", "H-XCHAIN", "H-CORR", "H-COINBASE", "H-TEMPORAL", "H-TAINT", "H-OSINT",
    "H-NETWORK",
}


def test_heuristic_ids_are_the_contract_used_by_detectors():
    assert {h.id for h in load_catalog(catalog_dir()).heuristics} == EXPECTED


def test_children_point_to_parents():
    cat = load_catalog(catalog_dir())
    for h in cat.heuristics:
        if h.id.startswith("H-CHG-"):
            assert h.parent == "H-CHG"
        if h.id.startswith("H-CJ-") and h.id != "H-CJ-POST":
            assert h.parent == "H-CJ"
