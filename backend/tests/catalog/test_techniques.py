from btcintel.catalog.loader import load_catalog
from btcintel.paths import catalog_dir

EXPECTED_BY_TACTIC = {
    "acquisition": {"O-KEY-COMPROMISE", "O-WEAK-KEY-SWEEP", "O-PROTOCOL-EXPLOIT", "O-SOCIAL-ENGINEERING", "O-RANSOM"},
    "layering": {"O-PEEL-CHAIN", "O-DISPERSAL", "O-DORMANCY", "O-RICOCHET"},
    "obfuscation": {"O-CUSTODIAL-MIXER", "O-COINJOIN", "O-PAYJOIN", "O-DARKNET-AS-MIXER", "O-SCRIPT-PRIVACY", "O-CHANGE-AVOIDANCE"},
    "chain_hopping": {"O-CHAIN-HOP", "O-INSTANT-SWAP", "O-PRIVACY-COIN"},
    "offchain": {"O-LIGHTNING", "O-SIDECHAIN", "O-ECASH"},
    "integration": {"O-NESTED-SERVICE", "O-OTC-P2P", "O-HIGH-RISK-EXCHANGE", "O-FAKE-KYC"},
}


def test_techniques_by_tactic():
    cat = load_catalog(catalog_dir())
    got: dict[str, set[str]] = {}
    for t in cat.techniques:
        got.setdefault(t.tactic, set()).add(t.id)
    assert got == EXPECTED_BY_TACTIC


def test_every_non_acquisition_technique_names_detection_or_says_why_not():
    cat = load_catalog(catalog_dir())
    for t in cat.techniques:
        if t.tactic != "acquisition" and not t.detected_by:
            # detection relies on address tags (labels) — must be stated in the summary
            assert "tag" in t.summary.lower(), t.id
