"""The tradingagents command."""

import argparse
import json
import sys

from tradingagents.data.errors import TradingAgentsError
from tradingagents.data.filings import load_filings
from tradingagents.data.ledger import ScoreResult, append_record, score_ledger
from tradingagents.data.prices import snapshot_text
from tradingagents.data.rundir import prepare_run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tradingagents")
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("ticker")
    snap.set_defaults(func=_snapshot)
    fil = sub.add_parser("filings")
    fil.add_argument("ticker")
    fil.set_defaults(func=_filings)
    rec = sub.add_parser("record")
    rec.add_argument("ticker")
    rec.add_argument("rating")
    rec.set_defaults(func=_record)
    scr = sub.add_parser("score")
    scr.set_defaults(func=_score)
    run = sub.add_parser(
        "run-dir",
        help="create an empty .tradingagents/<TICKER>/<local-date>/<HHMMSS>/ run directory",
    )
    run.add_argument("ticker")
    run.set_defaults(func=_run_dir)
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except TradingAgentsError as exc:
        print(exc, file=sys.stderr)
        return 1
    if isinstance(result, ScoreResult):
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.code
    print(result)
    return 0


def _snapshot(args) -> str:
    return snapshot_text(args.ticker)


def _filings(args) -> str:
    return load_filings(args.ticker)


def _record(args) -> str:
    return json.dumps(append_record(args.ticker, args.rating), indent=2)


def _score(args) -> ScoreResult:
    return score_ledger()


def _run_dir(args) -> str:
    return str(prepare_run_dir(args.ticker))


if __name__ == "__main__":
    sys.exit(main())
