import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from desk.cli import main
from desk.data.prices import snapshot_text


def _frame():
    return pd.DataFrame({
        "Date": pd.to_datetime(["2026-11-02"]),
        "Open": [187.0], "High": [188.0], "Low": [186.0], "Close": [187.25],
        "Volume": [1000],
    })


def _patch_snapshot(monkeypatch):
    text = snapshot_text(
        "NVDA",
        frame=_frame(),
        now=datetime(2026, 11, 3, tzinfo=ZoneInfo("America/New_York")),
    )
    monkeypatch.setattr("desk.data.ledger.snapshot_text", lambda ticker: text)


def test_hold_stores_the_snapshot_close(monkeypatch, tmp_path, capsys):
    _patch_snapshot(monkeypatch)
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    code = main(["record", "NVDA", "Hold"])
    row = json.loads(ledger.read_text(encoding="utf-8"))
    assert code == 0
    assert row["rating"] == "Hold"
    assert row["anchor_close"] == 187.25
    assert row["anchor_date"] == "2026-11-02"
    assert row["benchmark"] == "SPY"
    assert row["ret_5"] is None and row["ret_21"] is None
    assert "187.25" in capsys.readouterr().out


def test_lowercase_rating_is_canonical(monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch)
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    assert main(["record", "NVDA", "buy"]) == 0
    assert json.loads(ledger.read_text(encoding="utf-8"))["rating"] == "Buy"


def test_bad_ratings_write_nothing(monkeypatch, tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)

    def explode(ticker):
        raise AssertionError("snapshot ran")

    monkeypatch.setattr("desk.data.ledger.snapshot_text", explode)
    for rating in ("REVIEW", "Maybe"):
        assert main(["record", "NVDA", rating]) == 1
    assert not ledger.exists()


def test_snapshot_failure_writes_nothing(monkeypatch, tmp_path):
    from desk.data.errors import NoMarketDataError
    monkeypatch.setattr("desk.data.ledger.LEDGER", tmp_path / "ledger.jsonl")

    def fail(ticker):
        raise NoMarketDataError("no prices")

    monkeypatch.setattr("desk.data.ledger.snapshot_text", fail)
    assert main(["record", "NVDA", "Hold"]) == 1
    assert not (tmp_path / "ledger.jsonl").exists()


def test_two_records_are_two_lines(monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch)
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    assert main(["record", "NVDA", "Buy"]) == 0
    assert main(["record", "NVDA", "Sell"]) == 0
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_failed_replace_leaves_ledger_bytes_unchanged(monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch)
    ledger = tmp_path / "ledger.jsonl"
    seed = '{"id":"seed-row"}\n'
    ledger.write_text(seed, encoding="utf-8")
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    real_replace = Path.replace

    def fail_on_ledger_replace(self, target, *args, **kwargs):
        if target == ledger:
            raise OSError("replace failed")
        return real_replace(self, target, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", fail_on_ledger_replace)
    with pytest.raises(OSError, match="replace failed"):
        main(["record", "NVDA", "Hold"])
    assert ledger.read_text(encoding="utf-8") == seed
