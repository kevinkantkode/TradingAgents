import json
from datetime import date, timedelta

import pandas as pd

from desk.cli import main
from desk.data.errors import VendorUnavailableError


def _row(anchor=date(2026, 1, 2), close=100.0):
    return {
        "id": "row-1",
        "decided_at": "2026-01-02T00:00:00+00:00",
        "ticker": "NVDA",
        "rating": "Buy",
        "anchor_date": anchor.isoformat(),
        "anchor_close": close,
        "benchmark": "SPY",
        "ret_5": None, "alpha_5": None, "exit_date_5": None,
        "ret_21": None, "alpha_21": None, "exit_date_21": None,
    }


def _series(anchor: date, n: int, start: float, step: float):
    days = [anchor + timedelta(days=i + 1) for i in range(n)]
    return pd.Series([start + step * i for i in range(n)], index=days)


def _write(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_five_sessions_fill_only_the_short_horizon(monkeypatch, tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    _write(ledger, [_row(anchor)])
    stock = _series(anchor, 5, 110, 0)
    spy_index = [anchor, *list(_series(anchor, 5, 400, 0).index)]
    spy = pd.Series([400.0] * len(spy_index), index=spy_index)

    def closes_for(canonical):
        return stock if canonical == "NVDA" else spy

    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    monkeypatch.setattr("desk.data.ledger.closes_for", closes_for)
    assert main(["score"]) == 0
    saved = json.loads(ledger.read_text(encoding="utf-8"))
    assert saved["ret_5"] == (110 / 100) - 1
    assert saved["exit_date_5"] == (anchor + timedelta(days=5)).isoformat()
    assert saved["alpha_5"] == saved["ret_5"] - ((400 / 400) - 1)
    assert saved["ret_21"] is None
    out = capsys.readouterr().out.lower()
    assert "reflection" not in out
    assert "buy" not in out


def test_second_run_does_not_change_a_filled_horizon(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    row = _row(anchor)
    row["ret_5"] = 0.5
    row["alpha_5"] = 0.25
    row["exit_date_5"] = "2026-01-09"
    _write(ledger, [row])
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    monkeypatch.setattr(
        "desk.data.ledger.closes_for",
        lambda canonical: _series(anchor, 21, 1, 1),
    )
    assert main(["score"]) == 0
    saved = json.loads(ledger.read_text(encoding="utf-8"))
    assert saved["ret_5"] == 0.5
    assert saved["ret_21"] is not None


def test_short_series_stays_empty_and_exits_0(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    _write(ledger, [_row(anchor)])
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    monkeypatch.setattr("desk.data.ledger.closes_for", lambda canonical: _series(anchor, 3, 10, 0))
    assert main(["score"]) == 0
    saved = json.loads(ledger.read_text(encoding="utf-8"))
    assert saved["ret_5"] is None


def test_a_failed_fetch_of_a_sibling_does_not_drop_a_good_row(monkeypatch, tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    good = _row(anchor)
    bad = _row(anchor)
    bad["id"] = "row-2"
    bad["ticker"] = "AAPL"
    _write(ledger, [good, bad])
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)

    def closes_for(canonical):
        if canonical == "AAPL":
            raise VendorUnavailableError("down")
        return _series(anchor, 5, 110, 0)

    monkeypatch.setattr("desk.data.ledger.closes_for", closes_for)
    assert main(["score"]) == 1
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    by_id = {row["id"]: row for row in rows}
    assert by_id["row-1"]["ret_5"] == (110 / 100) - 1
    assert by_id["row-2"]["ret_5"] is None
    assert "AAPL" in capsys.readouterr().err


def test_missing_spy_cover_still_writes_the_raw_return(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    _write(ledger, [_row(anchor)])
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)

    def closes_for(canonical):
        if canonical == "SPY":
            return pd.Series(dtype=float)
        return _series(anchor, 5, 110, 0)

    monkeypatch.setattr("desk.data.ledger.closes_for", closes_for)
    assert main(["score"]) == 0
    saved = json.loads(ledger.read_text(encoding="utf-8"))
    assert saved["ret_5"] == (110 / 100) - 1
    assert saved["alpha_5"] is None
