import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from desk.cli import main
from desk.data.errors import VendorUnavailableError
from desk.data.ledger import score_ledger


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


def _ohlcv_frame(dates, closes):
    return pd.DataFrame({
        "Date": pd.to_datetime(dates),
        "Open": closes,
        "High": [c + 1 for c in closes],
        "Low": [c - 1 for c in closes],
        "Close": closes,
        "Volume": [1000] * len(closes),
    })


def test_open_session_is_not_the_nth_closed_bar(monkeypatch, tmp_path):
    spy_dates = [
        "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24",
        "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31",
        "2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04",
    ]
    spy_closes = [400.0 + i for i in range(len(spy_dates))]
    spy_frame = _ohlcv_frame(spy_dates, spy_closes)

    nvda_frame = _ohlcv_frame(
        ["2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-11-02"],
        [110.0, 111.0, 112.0, 113.0, 114.0],
    )
    sh_frame = _ohlcv_frame(
        ["2026-10-31", "2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"],
        [210.0, 211.0, 212.0, 213.0, 214.0],
    )
    frames = {"NVDA": nvda_frame, "600519.SS": sh_frame, "SPY": spy_frame}

    monkeypatch.setattr(
        "desk.data.ledger.fetch_daily",
        lambda canonical: frames[canonical],
    )

    ledger_nvda = tmp_path / "nvda.jsonl"
    _write(ledger_nvda, [_row(anchor=date(2026, 10, 26), close=100.0)])
    now_nvda = datetime(2026, 11, 2, 15, tzinfo=ZoneInfo("America/New_York"))
    result = score_ledger(ledger=ledger_nvda, now=now_nvda)
    assert result.code == 0
    nvda_row = json.loads(ledger_nvda.read_text(encoding="utf-8").strip())
    assert nvda_row["ret_5"] is None
    assert nvda_row["exit_date_5"] is None

    ledger_sh = tmp_path / "sh.jsonl"
    sh_row = _row(anchor=date(2026, 10, 30), close=200.0)
    sh_row["ticker"] = "600519.SS"
    _write(ledger_sh, [sh_row])
    now_sh = datetime(2026, 11, 4, 9, tzinfo=ZoneInfo("Asia/Shanghai"))
    result_sh = score_ledger(ledger=ledger_sh, now=now_sh)
    assert result_sh.code == 0
    sh_saved = json.loads(ledger_sh.read_text(encoding="utf-8").strip())
    assert sh_saved["ret_5"] is None
    assert sh_saved["exit_date_5"] is None


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


def test_spy_fetch_error_still_writes_the_raw_return(monkeypatch, tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    _write(ledger, [_row(anchor)])
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)

    def closes_for(canonical):
        if canonical == "SPY":
            raise VendorUnavailableError("spy down")
        return _series(anchor, 5, 110, 0)

    monkeypatch.setattr("desk.data.ledger.closes_for", closes_for)
    assert main(["score"]) == 1
    saved = json.loads(ledger.read_text(encoding="utf-8"))
    assert saved["ret_5"] == (110 / 100) - 1
    assert saved["exit_date_5"] == (anchor + timedelta(days=5)).isoformat()
    assert saved["alpha_5"] is None
    err = capsys.readouterr().err
    assert "ret_5" in err
    assert "spy down" in err


def test_fifth_closed_session_skips_weekend(monkeypatch, tmp_path):
    """Score through fetch_daily + drop_open_session, not a stubbed calendar series."""
    anchor = date(2026, 3, 6)  # Friday
    ledger = tmp_path / "ledger.jsonl"
    row = _row(anchor=anchor, close=100.0)
    _write(ledger, [row])
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)

    nvda_dates = [
        "2026-03-06",
        "2026-03-09",
        "2026-03-10",
        "2026-03-11",
        "2026-03-12",
        "2026-03-13",
    ]
    nvda_closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    nvda_frame = _ohlcv_frame(nvda_dates, nvda_closes)
    spy_frame = _ohlcv_frame(nvda_dates, [400.0] * len(nvda_dates))

    def fetch(canonical):
        if canonical == "SPY":
            return spy_frame
        if canonical == "NVDA":
            return nvda_frame
        raise AssertionError(f"unexpected ticker {canonical}")

    monkeypatch.setattr("desk.data.ledger.fetch_daily", fetch)
    now = datetime(2026, 3, 16, 12, tzinfo=ZoneInfo("America/New_York"))
    result = score_ledger(ledger=ledger, now=now)
    assert result.code == 0
    saved = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert saved["exit_date_5"] == "2026-03-13"
    assert saved["ret_5"] == pytest.approx(0.05)
    assert saved["ret_21"] is None
