"""Live end-to-end check against published incident seeds (network)."""

import pytest

from btcintel.catalog.loader import load_catalog
from btcintel.config import load_settings
from btcintel.runtime import open_runtime
from btcintel.trace.engine import TracePolicy, TraceSeed, trace

pytestmark = pytest.mark.network


async def test_trace_from_every_incident_seed_completes():
    settings = load_settings()
    cat = load_catalog(settings.catalog_dir)
    seeds = [(inc.id, s) for inc in cat.incidents for s in inc.seeds][:5]
    assert seeds, "Plan 1 Task 7 should have produced incident seeds"
    async with open_runtime(settings) as rt:
        for incident_id, s in seeds:
            seed = TraceSeed(txid=s.value) if s.kind == "tx" else TraceSeed(address=s.value)
            result = await trace(seed, TracePolicy(max_hops=2, max_calls=60, max_txs=30),
                                 chain=rt.chain, labels=rt.labels())
            assert result.txs_expanded >= 1, incident_id
