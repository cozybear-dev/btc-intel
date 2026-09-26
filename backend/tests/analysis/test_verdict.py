from btcintel.analysis.models import Bucket, ClusterSummary, Exposure, Reason
from btcintel.analysis.verdict import build_verdict
from btcintel.catalog.loader import load_catalog
from btcintel.cluster.expand import Conflict
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir
from tests.builders import ADDR

TAX = Taxonomy.from_catalog(load_catalog(catalog_dir()))
A = ADDR[1]


def bucket(label, key, risk, share, *, hops=2, kind="labeled", source="p", total=1_000_000):
    return Bucket(kind=kind, key=key, label=label, risk=risk, source=source, amount=share * total, share=share,
                  min_hops=hops)


def exposure(direction, *buckets, total=1_000_000):
    resolved = sum(b.share for b in buckets if b.kind != "remainder")
    return Exposure(direction=direction, total=total, buckets=list(buckets), resolved_share=resolved)


def verdict(*exposures, info=None, cluster=None, final=True):
    return build_verdict(A, info or {"tags": []}, cluster, list(exposures), taxonomy=TAX, hops=3, final=final)


def tag(address, label, category, abuse=None, pack="p"):
    return {"address": address, "label": label, "category": category, "abuse": abuse, "pack": pack}


def test_own_severe_label_is_severe_even_before_tracing():
    v = verdict(info={"tags": [tag(A, "OFAC: Garantex", "organization", "sanctioned", "ofac_sdn")]}, final=False)
    assert v.level == "severe" and v.reasons[0].rule == "own_label"
    assert v.reasons[0].text == "Labeled OFAC: Garantex (sanctioned, ofac_sdn)"
    assert not v.final and v.coverage == "Tracing in progress…" and not v.low_confidence


def test_cluster_label_is_lowered_when_the_cluster_has_conflicts():
    info = {"tags": [tag(ADDR[5], "Helix", "mixing_service")]}
    clean = ClusterSummary(root=A, size=12, partial=False, capped=False)
    v = verdict(info=info, cluster=clean)
    assert v.level == "high" and v.reasons[0].text == "Its co-spend cluster (12 addresses) includes Helix (mixing_service, p)"
    messy = clean.model_copy(update={"conflicts": [Conflict(labels=["binance", "helix"], addresses=[A])]})
    v = verdict(info=info, cluster=messy)
    assert v.level == "medium" and "conflicting labels" in v.reasons[0].text


def test_direct_severe_exposure():
    v = verdict(exposure("backward", bucket("LockBit", "ransomware", "severe", 0.05, hops=1, source="ransomwhere")))
    assert v.level == "severe"
    assert v.reasons[0].text == "Received 0.0005 BTC directly from LockBit (ransomware, ransomwhere)"


def test_high_risk_share_thresholds():
    high = verdict(exposure("forward", bucket("Helix", "mixing_service", "high", 0.2)))
    assert high.level == "high" and high.reasons[0].rule == "high_share"
    assert high.reasons[0].text == "20% of outgoing funds (0.002 BTC) went to high-risk entities: Helix (within 2 hops)"
    minor = verdict(exposure("forward", bucket("Helix", "mixing_service", "high", 0.04)))
    assert minor.level == "medium" and minor.reasons[0].rule == "high_minor"


def test_medium_share_thresholds():
    cj = bucket("CoinJoin (whirlpool)", "whirlpool", "medium", 0.3, kind="coinjoin", source=None)
    assert verdict(exposure("forward", cj)).level == "medium"
    v = verdict(exposure("forward", cj.model_copy(update={"share": 0.1, "amount": 100_000})))
    assert v.level == "low" and v.reasons[0].rule == "medium_minor"


def test_only_low_risk_entities_is_low():
    v = verdict(exposure("backward", bucket("Binance", "exchange", "low", 0.6)))
    assert v.level == "low"
    assert v.reasons == [Reason(level="low", rule="low_only",
                                text="Incoming funds came from only low-risk known entities: Binance")]


def test_nothing_found_and_low_coverage():
    unspent = bucket("Still unspent", "unspent", "none", 0.3, kind="unspent", source=None)
    unresolved = bucket("Fees or not reached (budget)", "remainder", "none", 0.7, kind="remainder", source=None)
    v = verdict(exposure("forward", unspent, unresolved))
    assert v.level == "none" and v.reasons[0].text == "No known entity found within 3 hops"
    assert v.low_confidence
    assert v.coverage == "Traced 30% of funds to an endpoint within 3 hops; 70% not reached"


def test_reasons_are_sorted_worst_first():
    v = verdict(exposure("backward", bucket("Binance", "exchange", "low", 0.6)),
                exposure("forward", bucket("Helix", "mixing_service", "high", 0.2)))
    assert [r.level for r in v.reasons] == ["high", "low"] and v.level == "high"


def test_no_incoming_funds():
    v = verdict(exposure("backward", total=0), exposure("forward", total=0))
    assert v.level == "none" and not v.low_confidence and v.coverage.startswith("No incoming funds")
