from btcintel.catalog.loader import load_catalog
from btcintel.paths import catalog_dir

# GraphSense / INTERPOL DW-VA taxonomy concept ids (graphsense.github.io/DW-VA-Taxonomy, fetched 2026-09-25)
GS_ENTITIES = ["organization", "user", "item", "service", "victim", "perpetrator", "donation", "exchange", "wallet_service", "escrow_wallet", "ico_wallet", "cold_wallet", "filesharing", "index", "market", "messaging_service", "mixing_service", "coinjoin", "miner", "mining_service", "gambling", "search_engine", "shop", "faucet", "payment_processor", "atm", "hosting", "vpn", "defi", "defi_lending", "defi_dex", "defi_derivative", "collectible"]
GS_ABUSES = ["scam", "extortion", "sextortion", "phishing", "service_hack", "ransomware", "investment_fraud", "ponzi_scheme", "pyramid_scheme", "sanction", "extremism", "terrorism", "dark_web"]

REQUIRED_IDS = {
    "exchange", "high_risk_exchange", "instant_exchange", "p2p_exchange", "otc_broker",
    "mixing_service", "coinjoin", "bridge", "gambling", "darknet_market", "mining_pool",
    "sanctioned", "ransomware", "theft", "scam", "unknown",
}


def test_every_graphsense_concept_is_mapped():
    cat = load_catalog(catalog_dir())
    mapped = {c for cat_ in cat.categories for c in cat_.gs_concepts}
    missing = sorted(set(GS_ENTITIES + GS_ABUSES) - mapped)
    assert missing == []


def test_required_category_ids_exist():
    cat = load_catalog(catalog_dir())
    assert {c.id for c in cat.categories} >= REQUIRED_IDS


def test_abuse_categories_are_high_or_severe():
    cat = load_catalog(catalog_dir())
    for c in cat.categories:
        if c.kind == "abuse":
            assert c.risk in {"high", "severe"}, c.id
