"""Ransomware payer -> analysed address -> exchange / unspent: the graph the analysis tests run on."""

from collections.abc import Iterable
from dataclasses import dataclass

from btcintel.analysis.models import AnalysisPolicy
from btcintel.analysis.run import analyze_address
from btcintel.catalog.loader import load_catalog
from btcintel.chain.models import Tx
from btcintel.cluster.unionfind import UnionFind
from btcintel.db import open_intel_db
from btcintel.labels.store import Tag, TagStore
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir
from tests.builders import ADDR, mk_tx
from tests.scenario import EX, U, scenario_tags

A, R = ADDR[1], ADDR[9]
TAX = Taxonomy.from_catalog(load_catalog(catalog_dir()))


@dataclass
class Funded:
    cb: Tx
    pay: Tx
    spend: Tx

    @property
    def txs(self) -> list[Tx]:
        return [self.cb, self.pay, self.spend]


def build_funded() -> Funded:
    """R (ransomware, mined coins) pays A 1.5M; A pays EX (exchange) 1M and U 499k (left unspent)."""
    cb = mk_tx([(None, 0)], [(R, 2_000_000)], coinbase=True)
    pay = mk_tx([(cb, 0)], [(A, 1_500_000), (R, 499_000)])
    spend = mk_tx([(pay, 0)], [(EX, 1_000_000), (U, 499_000)])
    return Funded(cb, pay, spend)


def ransomware_tag() -> Tag:
    # category "unknown" + abuse "ransomware": the shape of most imported ransomware tags
    return Tag(address=R, label="LockBit", category="unknown", abuse="ransomware", confidence="forensic",
               source="test", pack="ransomwhere")


def stores(tagged: bool = True, *, extra_tags: Iterable[Tag] = ()) -> tuple[TagStore, UnionFind]:
    conn = open_intel_db(":memory:")
    tags = TagStore(conn)
    tags.add_many([*scenario_tags(), *([ransomware_tag()] if tagged else []), *extra_tags])
    return tags, UnionFind(conn)


async def run_analysis(chain, *, address=A, tagged=True, policy=None, extra_tags: Iterable[Tag] = ()):
    tags, uf = stores(tagged, extra_tags=extra_tags)
    events: list[dict] = []
    report = await analyze_address(address, policy or AnalysisPolicy.quick(), chain=chain, tags=tags, uf=uf,
                                   taxonomy=TAX, emit=events.append)
    return report, events
