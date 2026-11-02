"""Decision ledger. Scores are filled later and never sent back to a desk."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from desk.data.errors import DeskError
from desk.data.prices import snapshot_text

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
