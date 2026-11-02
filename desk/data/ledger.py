"""Decision ledger. Scores are filled later and never sent back to a desk."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from desk.data.errors import DeskError
from desk.data.prices import fetch_daily, snapshot_text

HORIZONS = (5, 21)

LEDGER = Path.home() / ".tradingagents" / "ledger.jsonl"
RATINGS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")


def parse_rating(text: str) -> str:
    match = {name.lower(): name for name in RATINGS}
    found = match.get(text.strip().lower())
    if found is None:
        raise DeskError(f"rating must be one of {', '.join(RATINGS)}")
    return found


def parse_snapshot_marker(text: str) -> tuple[str, str, float]:
    try:
        kind, ticker, anchor_date, close = text.splitlines()[0].split()
    except (IndexError, ValueError) as exc:
        raise DeskError("snapshot did not start with a SNAPSHOT line") from exc
    if kind != "SNAPSHOT":
        raise DeskError("snapshot did not start with a SNAPSHOT line")
    return ticker, anchor_date, float(close)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def append_record(ticker: str, rating: str, *, ledger: Path | None = None) -> dict:
    canonical_rating = parse_rating(rating)
    path = ledger or LEDGER
    text = snapshot_text(ticker)
    symbol, anchor_date, close = parse_snapshot_marker(text)
    row = {
        "id": str(uuid.uuid4()),
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "ticker": symbol,
        "rating": canonical_rating,
        "anchor_date": anchor_date,
        "anchor_close": close,
        "benchmark": "SPY",
        "ret_5": None,
        "alpha_5": None,
        "exit_date_5": None,
        "ret_21": None,
        "alpha_21": None,
        "exit_date_21": None,
    }
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    _write(path, existing + json.dumps(row) + "\n")
    return row


def closes_for(canonical: str) -> pd.Series:
    frame = fetch_daily(canonical)
    dates = pd.to_datetime(frame["Date"]).dt.date
    series = pd.Series(frame["Close"].astype(float).to_numpy(), index=list(dates))
    series = series[series > 0]
    return series.sort_index()


def _nth_later(series: pd.Series, anchor: date, n: int):
    later = [(day, float(price)) for day, price in series.items() if day > anchor]
    if len(later) < n:
        return None
    return later[n - 1]


def _spy_return(spy: pd.Series, anchor: date, exit_day: date) -> float | None:
    before = [(day, price) for day, price in spy.items() if day <= anchor]
    after = [(day, price) for day, price in spy.items() if day <= exit_day]
    if not before or not after:
        return None
    start, end = before[-1][1], after[-1][1]
    if start <= 0:
        return None
    return (end / start) - 1


class ScoreResult(NamedTuple):
    stdout: str
    code: int
    stderr: str


def _filled(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def score_ledger(*, ledger: Path | None = None) -> ScoreResult:
    path = ledger or LEDGER
    if not path.exists():
        return ScoreResult("", 0, "")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    stdout_lines = []
    stderr_lines = []
    for row in rows:
        touched = False
        anchor = date.fromisoformat(row["anchor_date"])
        try:
            stock = closes_for(row["ticker"])
            spy = closes_for(row["benchmark"])
        except DeskError as exc:
            stderr_lines.append(f"{row['ticker']} {row['id']}: {exc}")
            continue
        for n in HORIZONS:
            key = f"ret_{n}"
            if _filled(row.get(key)):
                continue
            found = _nth_later(stock, anchor, n)
            if found is None:
                continue
            exit_day, exit_close = found
            raw = (exit_close / float(row["anchor_close"])) - 1
            row[key] = raw
            row[f"exit_date_{n}"] = exit_day.isoformat()
            bench = _spy_return(spy, anchor, exit_day)
            row[f"alpha_{n}"] = None if bench is None else raw - bench
            touched = True
            stdout_lines.append(f"scored {row['id']} ret_{n}")
        if not touched and not any(_filled(row.get(f"ret_{n}")) for n in HORIZONS):
            stdout_lines.append(f"skipped {row['id']}")
    _write(path, "".join(json.dumps(row) + "\n" for row in rows))
    return ScoreResult("\n".join(stdout_lines), 1 if stderr_lines else 0, "\n".join(stderr_lines))
