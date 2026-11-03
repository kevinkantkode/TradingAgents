"""Dispatcher prompt and the result check for a tradingagents run."""

from __future__ import annotations

from pathlib import Path

from tradingagents.data.errors import TradingAgentsError
from tradingagents.data.ledger import RATINGS
from tradingagents.data.symbols import safe_ticker_component


def dispatcher_prompt(ticker: str) -> str:
    safe = safe_ticker_component(ticker.strip())
    return (
        "You are the TradingAgents dispatcher. Follow the skill at "
        ".cursor/skills/tradingagents/SKILL.md exactly.\n\n"
        f"The ticker is: {safe}\n\n"
        "That ticker is the only task. Do not trade. Do not call a broker. "
        "Do not push, commit, or open a pull request. Do not modify files outside "
        "the run directory the skill creates, except the ledger write performed "
        "by the skill's record command.\n"
    )


def assert_run_result(run_root: Path) -> str:
    files = sorted(run_root.rglob("rating.md"))
    if len(files) != 1:
        raise TradingAgentsError(f"expected one rating.md, found {len(files)}: {files}")
    lines = files[0].read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] not in RATINGS:
        raise TradingAgentsError(f"rating first line is not a rating: {lines[:1]!r}")
    return lines[0]


def new_run_directory(before: set[Path], after: set[Path]) -> Path:
    before_resolved = {path.resolve() for path in before}
    new = sorted(path.resolve() for path in after if path.resolve() not in before_resolved)
    if len(new) != 1:
        raise TradingAgentsError(f"expected one new rating.md, found {len(new)}: {new}")
    return new[0].parent
