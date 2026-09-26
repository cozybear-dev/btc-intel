"""Command-line entry point: `btcintel <command> ...`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from btcintel import __version__
from btcintel.catalog.loader import CatalogError, check_catalog, load_catalog
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
COMMANDS["catalog"] = _cmd_catalog


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="btcintel", description="Bitcoin intelligence toolkit")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the version")
    cat = sub.add_parser("catalog", help="knowledge-base catalog tools")
    cat_sub = cat.add_subparsers(dest="catalog_command", required=True)
    cat_sub.add_parser("check", help="validate catalog/*.yaml and docs/kb pages")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
