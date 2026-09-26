"""Command-line entry point: `btcintel <command> ...`."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable
from pathlib import Path

import httpx

from btcintel import __version__
from btcintel.catalog.loader import CatalogError, check_catalog, load_catalog
from btcintel.catalog.online import check_urls, verify_seeds
from btcintel.catalog.render import write_all
from btcintel.chain.errors import ChainError
from btcintel.chain.validate import classify_query, is_address, is_txid
from btcintel.config import load_settings
from btcintel.db import open_intel_db
from btcintel.labels import importers
from btcintel.labels.store import TagStore
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir, kb_dir


def _cmd_version(args: argparse.Namespace) -> int:
    print(__version__)
    return 0


# command name -> handler; later tasks add entries (and subparsers in _build_parser)
COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "version": _cmd_version,
}


def _cmd_catalog(args: argparse.Namespace) -> int:
    try:
        cat = load_catalog(catalog_dir())
    except CatalogError as e:
        print(f"catalog error: {e}", file=sys.stderr)
        return 1
    return CATALOG_COMMANDS[args.catalog_command](cat)


def _catalog_check(cat) -> int:
    problems = check_catalog(cat, kb_dir())
    for p in problems:
        print(p)
    print(
        f"{len(cat.heuristics)} heuristics, {len(cat.techniques)} techniques, "
        f"{len(cat.incidents)} incidents, {len(cat.references)} references: "
        f"{'OK' if not problems else f'{len(problems)} problem(s)'}",
        file=sys.stderr,
    )
    return 1 if problems else 0


CATALOG_COMMANDS = {"check": _catalog_check}


def _catalog_linkcheck(cat) -> int:
    problems = check_urls(r.url for r in cat.references)
    for url, why in problems:
        print(f"{why}\t{url}")
    return 1 if problems else 0


def _catalog_verify_seeds(cat) -> int:
    problems = verify_seeds(cat)
    for what, why in problems:
        print(f"{why}\t{what}")
    return 1 if problems else 0


CATALOG_COMMANDS.update({"linkcheck": _catalog_linkcheck, "verify-seeds": _catalog_verify_seeds})


def _catalog_render(cat) -> int:
    for path in write_all(cat, kb_dir()):
        print(f"wrote {path}")
    return 0


CATALOG_COMMANDS["render"] = _catalog_render


def _label_env():
    settings = load_settings()
    store = TagStore(open_intel_db(settings.intel_path))
    taxonomy = Taxonomy.from_catalog(load_catalog(settings.catalog_dir))
    return settings, store, taxonomy


def _cmd_import_tags(args: argparse.Namespace) -> int:
    settings, store, taxonomy = _label_env()
    source = args.source
    if source == "tagpack":
        if not args.path:
            print("a TagPack path is required", file=sys.stderr)
            return 2
        path = Path(args.path)
        report = importers.import_tagpack_text(store, taxonomy, path.read_text(encoding="utf-8"),
                                               args.pack or f"file:{path.stem}")
    else:
        url = {"graphsense": importers.GRAPHSENSE_TARBALL_URL, "ofac": importers.OFAC_SDN_URL,
               "pools": importers.POOLS_URL, "ransomwhere": importers.RANSOMWHERE_URL}[source]
        print(f"downloading {url} …", file=sys.stderr)
        try:
            data = importers.fetch(url, proxy=settings.proxy)
        except httpx.HTTPError as e:
            print(f"download failed: {e}", file=sys.stderr)
            return 1
        report = {
            "graphsense": lambda: importers.import_graphsense_tarball(store, taxonomy, data),
            "ofac": lambda: importers.import_ofac(store, data),
            "pools": lambda: importers.import_pools(store, data),
            "ransomwhere": lambda: importers.import_ransomwhere(store, data),
        }[source]()
    print(f"imported {report.tags} tags from {report.packs} pack(s); "
          f"{len(report.warnings)} warning(s), {len(report.errors)} error(s)")
    for line in (report.errors + report.warnings)[:20]:
        print(f"  {line}", file=sys.stderr)
    return 0


def _cmd_tags(args: argparse.Namespace) -> int:
    _, store, taxonomy = _label_env()
    tags = store.for_address(args.address)
    for t in tags:
        print(f"{t.label}\t{t.category}\t{t.abuse or '-'}\trisk={taxonomy.risk_of_tag(t)}\t"
              f"{t.confidence}\t{t.pack}\t{t.source}")
    if not tags:
        print("no tags")
    return 0


COMMANDS.update({"import-tags": _cmd_import_tags, "tags": _cmd_tags})
COMMANDS["catalog"] = _cmd_catalog


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from btcintel.api.app import create_app

    settings = load_settings()
    host = args.host or settings.host
    port = args.port or settings.port
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("WARNING: binding to a non-loopback address exposes an unauthenticated API", file=sys.stderr)
    uvicorn.run(create_app(settings), host=host, port=port, log_level="info")
    return 0


def _cmd_tx(args: argparse.Namespace) -> int:
    if not is_txid(args.txid):
        print("invalid txid", file=sys.stderr)
        return 2
    return asyncio.run(_tx(args.txid.lower()))


async def _tx(txid: str) -> int:
    from btcintel.heuristics.base import analyze_tx
    from btcintel.heuristics.flags import tx_flags
    from btcintel.runtime import open_runtime

    async with open_runtime(load_settings()) as rt:
        try:
            tx = await rt.chain.get_tx(txid)
            findings = await analyze_tx(tx, rt.context())
        except ChainError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(json.dumps({"txid": tx.txid, "flags": tx_flags(tx),
                          "findings": [f.model_dump() for f in findings]}, indent=2))
    return 0


def _cmd_trace(args: argparse.Namespace) -> int:
    kind, value = classify_query(args.seed)
    if kind not in ("txid", "outpoint", "address"):
        print("seed must be a txid, txid:vout or address", file=sys.stderr)
        return 2
    return asyncio.run(_trace(kind, value, args))


async def _trace(kind: str, value: str, args: argparse.Namespace) -> int:
    from btcintel.runtime import open_runtime
    from btcintel.trace.engine import TracePolicy, TraceSeed, trace

    if kind == "outpoint":
        txid, vout = value.split(":")
        seed = TraceSeed(txid=txid, vout=int(vout))
    elif kind == "txid":
        seed = TraceSeed(txid=value)
    else:
        seed = TraceSeed(address=value)
    policy = TracePolicy(direction="backward" if args.backward else "forward", max_hops=args.hops,
                         taint_model=args.model, peel_mode=args.peel, max_calls=args.max_calls,
                         coinjoin="through" if args.through_coinjoin else "stop")
    async with open_runtime(load_settings()) as rt:
        try:
            result = await trace(seed, policy, chain=rt.chain, labels=rt.labels())
        except ChainError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    order = {"labeled": 0, "coinjoin": 1, "unspent": 2}
    stops = sorted(result.stops, key=lambda st: (order.get(st.reason, 9), -st.taint))
    print(json.dumps({
        "txs": result.txs_expanded, "addresses": sum(n.kind == "address" for n in result.nodes),
        "incomplete": result.incomplete, "reason": result.reason, "calls_used": result.calls_used,
        "stops": [st.model_dump() for st in stops[:50]],
    }, indent=2))
    return 0


def _cmd_cluster(args: argparse.Namespace) -> int:
    if not is_address(args.address):
        print("invalid address", file=sys.stderr)
        return 2
    return asyncio.run(_cluster(args))


async def _cluster(args: argparse.Namespace) -> int:
    from btcintel.cluster.expand import ExpandPolicy, expand_cluster
    from btcintel.runtime import open_runtime

    async with open_runtime(load_settings()) as rt:
        result = await expand_cluster(args.address, rt.chain, rt.uf, rt.tags,
                                      ExpandPolicy(max_addresses=args.max_addresses, max_calls=args.max_calls))
    print(json.dumps(result.model_dump(), indent=2))
    return 0


COMMANDS.update({"serve": _cmd_serve, "tx": _cmd_tx, "trace": _cmd_trace, "cluster": _cmd_cluster})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="btcintel", description="Bitcoin intelligence toolkit")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the version")
    cat = sub.add_parser("catalog", help="knowledge-base catalog tools")
    cat_sub = cat.add_subparsers(dest="catalog_command", required=True)
    cat_sub.add_parser("check", help="validate catalog/*.yaml and docs/kb pages")
    cat_sub.add_parser("linkcheck", help="(network) check that reference URLs resolve")
    cat_sub.add_parser("verify-seeds", help="(network) check incident seeds exist on chain")
    cat_sub.add_parser("render", help="regenerate docs/kb/index.md and ttp-matrix.md")
    imp = sub.add_parser("import-tags", help="import attribution tags")
    imp.add_argument("source", choices=["graphsense", "ofac", "pools", "ransomwhere", "tagpack"])
    imp.add_argument("path", nargs="?", help="TagPack YAML file (source=tagpack)")
    imp.add_argument("--pack", help="pack name for a TagPack file")
    tg = sub.add_parser("tags", help="show tags for an address")
    tg.add_argument("address")
    sv = sub.add_parser("serve", help="run the local API (and web UI if built)")
    sv.add_argument("--host")
    sv.add_argument("--port", type=int)
    txp = sub.add_parser("tx", help="analyze one transaction")
    txp.add_argument("txid")
    tr = sub.add_parser("trace", help="trace funds from a txid, txid:vout or address")
    tr.add_argument("seed")
    tr.add_argument("--backward", action="store_true")
    tr.add_argument("--hops", type=int, default=6)
    tr.add_argument("--model", choices=["haircut", "fifo", "poison"], default="haircut")
    tr.add_argument("--peel", action="store_true", help="follow only the remainder (peel chains)")
    tr.add_argument("--max-calls", type=int, default=600)
    tr.add_argument("--through-coinjoin", action="store_true")
    cl = sub.add_parser("cluster", help="expand the CIOH cluster of an address")
    cl.add_argument("address")
    cl.add_argument("--max-addresses", type=int, default=2000)
    cl.add_argument("--max-calls", type=int, default=400)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
