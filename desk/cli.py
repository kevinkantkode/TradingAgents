"""The desk command."""

import argparse
import sys

from desk.data.errors import DeskError
from desk.data.filings import load_filings
from desk.data.prices import snapshot_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="desk")
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("ticker")
    snap.set_defaults(func=_snapshot)
    fil = sub.add_parser("filings")
    fil.add_argument("ticker")
    fil.set_defaults(func=_filings)
    args = parser.parse_args(argv)
    try:
        text = args.func(args)
    except DeskError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(text)
    return 0


def _snapshot(args) -> str:
    return snapshot_text(args.ticker)


def _filings(args) -> str:
    return load_filings(args.ticker)


if __name__ == "__main__":
    sys.exit(main())
