"""Command-line entry point: `btcintel <command> ...`."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from btcintel import __version__


def _cmd_version(args: argparse.Namespace) -> int:
    print(__version__)
    return 0


# command name -> handler; later tasks add entries (and subparsers in _build_parser)
COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "version": _cmd_version,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="btcintel", description="Bitcoin intelligence toolkit")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the version")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
