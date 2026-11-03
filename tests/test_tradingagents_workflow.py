from pathlib import Path

import pytest

from tradingagents.data.errors import TradingAgentsError
from tradingagents.run_result import assert_run_result, dispatcher_prompt


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
