"""A small theft → laundering graph used by trace and API tests."""

from dataclasses import dataclass

from btcintel.catalog.loader import load_catalog
from btcintel.chain.models import Tx
from btcintel.db import open_intel_db
from btcintel.labels.lookup import LabelLookup
from btcintel.labels.store import Tag, TagStore
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir
from tests.builders import ADDR, mk_tx

V, H1, H2, H3, EX, M, U = ADDR[0], ADDR[1], ADDR[4], ADDR[5], ADDR[2], ADDR[3], ADDR[8]
# ADDR entries scenario_tags() leaves untagged, for tests that must not hit a labeled stop.
UNTAGGED = [x for x in ADDR if x not in (EX, M)]


@dataclass
class Scenario:
    theft: Tx
    t1: Tx
    t2: Tx
    t3: Tx

    @property
    def txs(self) -> list[Tx]:
        return [self.theft, self.t1, self.t2, self.t3]


def build_scenario() -> Scenario:
    """V --theft--> H1 (600k) / H2 (399k); H1 -> EX (exchange, 100k) + H3 (499k) -> U (unspent);
    H2 -> M (mixer)."""
    theft = mk_tx([(V, 1_000_000)], [(H1, 600_000), (H2, 399_000)])
    t1 = mk_tx([(theft, 0)], [(EX, 100_000), (H3, 499_000)])
    t2 = mk_tx([(t1, 1)], [(U, 498_000)])
    t3 = mk_tx([(theft, 1)], [(M, 398_000)])
    return Scenario(theft, t1, t2, t3)


def scenario_tags() -> list[Tag]:
    return [
        Tag(address=EX, label="Example Exchange", category="exchange", confidence="authority_data",
            source="test", pack="test"),
        Tag(address=M, label="Example Mixer", category="mixing_service", confidence="authority_data",
            source="test", pack="test"),
    ]


def make_labels(extra_tags: list[Tag] | None = None, stop_categories=None) -> LabelLookup:
    store = TagStore(open_intel_db(":memory:"))
    store.add_many(scenario_tags() + (extra_tags or []))
    return LabelLookup(store, Taxonomy.from_catalog(load_catalog(catalog_dir())),
                       stop_categories=stop_categories)
