from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from desk.cli import main
from desk.data.prices import snapshot_text


def _bars(dates, closes):
    return pd.DataFrame({
        "Date": pd.to_datetime(dates),
        "Open": closes,
        "High": [c + 1 for c in closes],
        "Low": [c - 1 for c in closes],
        "Close": closes,
        "Volume": [1000] * len(closes),
    })


def test_marker_uses_the_last_closed_row_and_matches_the_table(monkeypatch, capsys):
    frame = _bars(["2026-10-30", "2026-11-02"], [10.0, 187.25])
    text = snapshot_text("nvda", frame=frame, now=datetime(2026, 11, 3, tzinfo=ZoneInfo("America/New_York")))
    first = text.splitlines()[0]
    assert first == "SNAPSHOT NVDA 2026-11-02 187.25"
    assert "187.25" in text.split("SNAPSHOT", 1)[1]


def test_todays_partial_bar_is_not_the_anchor():
    frame = _bars(["2026-11-02", "2026-11-03"], [187.25, 999.0])
    text = snapshot_text(
        "NVDA",
        frame=frame,
        now=datetime(2026, 11, 3, 15, tzinfo=ZoneInfo("America/New_York")),
    )
    assert text.splitlines()[0] == "SNAPSHOT NVDA 2026-11-02 187.25"
    assert "999" not in text


def test_empty_series_exits_1_without_a_marker(monkeypatch, capsys):
    monkeypatch.setattr("desk.data.prices.fetch_daily", lambda canonical: _bars([], []))
    code = main(["snapshot", "NVDA"])
    captured = capsys.readouterr()
    assert code == 1
    assert "SNAPSHOT" not in captured.out
    assert captured.err


def test_alias_is_the_symbol_the_vendor_is_asked(monkeypatch):
    seen = {}

    def fetch(canonical):
        seen["canonical"] = canonical
        return _bars(["2026-10-30"], [1900.0])

    monkeypatch.setattr("desk.data.prices.fetch_daily", fetch)
    snapshot_text("XAUUSD+", now=datetime(2026, 11, 3, tzinfo=ZoneInfo("America/New_York")))
    assert seen["canonical"] == "GC=F"


def test_unsafe_ticker_does_not_call_the_vendor(monkeypatch):
    def fetch(canonical):
        raise AssertionError("vendor was called")

    monkeypatch.setattr("desk.data.prices.fetch_daily", fetch)
    code = main(["snapshot", ".."])
    assert code == 1
