"""Static contract for the TradingAgents subagents and parent skill."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / ".cursor" / "agents"
SKILL = ROOT / ".cursor" / "skills" / "tradingagents" / "SKILL.md"

EXPECTED_AGENTS = {
    "aggressive.md",
    "bear.md",
    "bull.md",
    "conservative.md",
    "fundamentals.md",
    "market.md",
    "neutral.md",
    "news.md",
    "omissions.md",
    "portfolio-manager.md",
    "research-manager.md",
    "sentiment.md",
    "trader.md",
}

RATING_FORBIDDEN = "Buy, Overweight, Hold, Underweight, or Sell"


def test_agent_directory_is_the_expected_files():
    found = {path.name for path in AGENTS.glob("*.md")}
    assert found == EXPECTED_AGENTS


def test_market_agent_runs_snapshot():
    text = (AGENTS / "market.md").read_text(encoding="utf-8")
    assert "tradingagents snapshot" in text
    assert "SNAPSHOT" in text


def test_fundamentals_agent_runs_filings():
    text = (AGENTS / "fundamentals.md").read_text(encoding="utf-8")
    assert "tradingagents filings" in text
    assert "FILINGS" in text


def test_news_and_sentiment_do_not_run_tradingagents_cli():
    for name in ("news.md", "sentiment.md"):
        text = (AGENTS / name).read_text(encoding="utf-8")
        assert "Do not run `tradingagents`" in text


def test_portfolio_manager_emits_the_five_ratings():
    text = (AGENTS / "portfolio-manager.md").read_text(encoding="utf-8")
    for word in ("Buy", "Overweight", "Hold", "Underweight", "Sell"):
        assert word in text


def test_bull_and_bear_do_not_run_cli_or_emit_ratings():
    for name in ("bull.md", "bear.md"):
        text = (AGENTS / name).read_text(encoding="utf-8")
        assert "do not run `tradingagents`" in text
        assert RATING_FORBIDDEN in text


def test_trader_and_risk_agents_do_not_run_cli_or_use_rating_words():
    for name in ("trader.md", "aggressive.md", "conservative.md", "neutral.md"):
        text = (AGENTS / name).read_text(encoding="utf-8")
        assert "do not run `tradingagents`" in text
        assert RATING_FORBIDDEN in text


def test_research_manager_does_not_run_cli_or_use_rating_words():
    text = (AGENTS / "research-manager.md").read_text(encoding="utf-8")
    assert "do not run `tradingagents`" in text
    assert "Do not use the words Buy, Overweight, Hold, Underweight, or Sell" in text
    assert "OMISSION" in text
    assert "You may not open the analyst reports" in text


def test_omissions_agent_is_a_capped_diff():
    text = (AGENTS / "omissions.md").read_text(encoding="utf-8")
    assert "do not run `tradingagents`" in text
    assert RATING_FORBIDDEN in text
    assert "NONE" in text
    assert "OMISSION" in text
    assert "one to four lines" in text


def test_tradingagents_skill_lists_analysts_record_and_score_rule():
    text = SKILL.read_text(encoding="utf-8")
    for name in ("market", "fundamentals", "news", "sentiment"):
        assert f"`{name}`" in text
    assert "tradingagents run-dir" in text
    assert "tradingagents record" in text
    assert "You do not run `tradingagents score`" in text
    assert "`omissions`" in text
    assert "Do not pass `omissions.md`" in text
    for word in ("Buy", "Overweight", "Hold", "Underweight", "Sell"):
        assert word in text


def test_tradingagents_skill_uses_a_unique_run_directory():
    text = SKILL.read_text(encoding="utf-8")
    assert "<local-date>/<HHMMSS>/" in text
    assert "wipe" not in text.lower()


def test_run_directory_is_not_gitignored():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".tradingagents/" not in text
