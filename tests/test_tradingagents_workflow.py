from pathlib import Path

import pytest

from tradingagents.data.errors import TradingAgentsError
from tradingagents.run_result import assert_run_result, dispatcher_prompt, new_run_directory


def test_dispatcher_prompt_embeds_the_stripped_ticker():
    text = dispatcher_prompt(" aapl ")
    assert "The ticker is: aapl" in text
    assert "Do not call a broker." in text


def test_dispatcher_prompt_rejects_a_path():
    with pytest.raises(ValueError):
        dispatcher_prompt("../etc")


def test_assert_run_result_reads_the_rating_under_the_ticker_date(tmp_path: Path):
    day = tmp_path / "AAPL" / "2026-11-03"
    day.mkdir(parents=True)
    (day / "rating.md").write_text("Buy\n\nThe call:\n", encoding="utf-8")
    assert assert_run_result(tmp_path) == "Buy"


def test_assert_run_result_rejects_a_bad_first_line(tmp_path: Path):
    day = tmp_path / "AAPL" / "2026-11-03"
    day.mkdir(parents=True)
    (day / "rating.md").write_text("Maybe\n", encoding="utf-8")
    with pytest.raises(TradingAgentsError, match="not a rating"):
        assert_run_result(tmp_path)


def test_workflow_is_dispatch_only_and_publishes_the_run_folder():
    text = Path(".github/workflows/tradingagents.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "pull_request" not in text
    assert "schedule:" not in text
    assert "ROBINHOOD" not in text.upper()
    assert "CURSOR_API_KEY" in text
    assert "contents: read" in text
    assert "name: tradingagents" in text
    assert "ledger.jsonl" not in text


def test_new_run_directory_returns_the_one_new_parent(tmp_path: Path):
    old = tmp_path / "NVDA" / "2026-11-03" / "120000" / "rating.md"
    new = tmp_path / "NVDA" / "2026-11-03" / "120001" / "rating.md"
    old.parent.mkdir(parents=True)
    new.parent.mkdir(parents=True)
    old.write_text("Hold\n", encoding="utf-8")
    new.write_text("Buy\n", encoding="utf-8")
    assert new_run_directory({old}, {old, new}) == new.parent


def test_new_run_directory_rejects_none_or_two(tmp_path: Path):
    first = tmp_path / "a" / "rating.md"
    second = tmp_path / "b" / "rating.md"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("Buy\n", encoding="utf-8")
    second.write_text("Hold\n", encoding="utf-8")
    with pytest.raises(TradingAgentsError, match="found 0"):
        new_run_directory({first}, {first})
    with pytest.raises(TradingAgentsError, match="found 2"):
        new_run_directory(set(), {first, second})


def test_new_run_directory_treats_one_file_as_one_path(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    old = Path(".tradingagents/NVDA/2026-11-03/120000/rating.md")
    new = Path(".tradingagents/NVDA/2026-11-03/120001/rating.md")
    old.parent.mkdir(parents=True)
    new.parent.mkdir(parents=True)
    old.write_text("Buy\n", encoding="utf-8")
    new.write_text("Sell\n", encoding="utf-8")
    found = new_run_directory({old}, {old.resolve(), new.resolve()})
    assert found == new.resolve().parent
