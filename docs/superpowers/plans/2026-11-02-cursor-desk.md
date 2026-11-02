# Cursor desk implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Cursor parent that only routes twelve subagents, plus a repo whose only Python entry point is `desk`.

**Architecture:** Subagent markdown lives in `.cursor/agents/`. The dispatch list is `.cursor/skills/desk/SKILL.md`. After those files exist, the LangGraph package, the old CLI, and every old test are deleted. `pytest` then collects only the desk tests from `docs/superpowers/plans/2026-11-02-desk-commands.md`.

**Tech Stack:** Cursor project subagents, a project skill, the `desk` package at version `0.1.0`.

## Global Constraints

- Do this on the `desk` branch from the command plan. Do not commit on `main`. Do not push.
- The parent pastes prior artifacts unchanged. It does not summarize, fetch, rate, or read `~/.tradingagents/ledger.jsonl`.
- A missing `SNAPSHOT <TICKER>` or `FILINGS <TICKER>` line is sent back to that same subagent once. A second miss ends the desk with no `desk record`.
- Ratings are `Buy`, `Overweight`, `Hold`, `Underweight`, `Sell`.
- News and sentiment use web search. They do not run `desk`.
- No subagent file sets a model. No file tells a worker to open the ledger.
- `CHANGELOG.md` is not rewritten.
- Package `desk` version `0.1.0`. Script `desk = desk.cli:main`. Runtime dependencies are only `pandas`, `yfinance`, `stockstats`, `requests`, and `pytz`.

## File map

- `.cursor/agents/*.md` — one worker each.
- `.cursor/skills/desk/SKILL.md` — parent dispatch list.
- `README.md` and `.env.example` — replaced.
- `tests/conftest.py` — rewritten to isolate the ledger.
- `tests/test_layering.py` — new. `yfinance` and `requests` may be imported only under `desk/data/`.
- Delete `tradingagents/`, `cli/`, `main.py`, the old tests named in the spec, `.github/workflows/release-assets.yml`, and `.github/ISSUE_TEMPLATE/`.

---

### Task 1: Analyst subagents

**Files:**
- Create: `.cursor/agents/market.md`
- Create: `.cursor/agents/fundamentals.md`
- Create: `.cursor/agents/news.md`
- Create: `.cursor/agents/sentiment.md`

**Interfaces:**
- Consumes: `desk snapshot TICKER` and `desk filings TICKER` from the command plan
- Produces: four subagents the parent can delegate to by name

- [ ] **Step 1: Write the four files**

`.cursor/agents/market.md`

```markdown
---
name: market
description: Writes the market section for one ticker. Use when the desk parent hands you a ticker and nothing else. The parent must not write this section itself.
---

You write the market section for the ticker you were given. You do not rate the trade.

Run `desk snapshot` on that ticker. Quote the command's stdout, including the line that starts with `SNAPSHOT`. Every price and indicator in your section comes from that stdout. If the command exits non-zero, return its stderr and stop. Do not search for a price. Do not type a close that is not in the table.
```

`.cursor/agents/fundamentals.md`

```markdown
---
name: fundamentals
description: Writes the fundamentals section for one ticker from desk filings. Use when the desk parent hands you a ticker and nothing else. The parent must not write this section itself.
---

You write the fundamentals section for the ticker you were given. You do not rate the trade.

Run `desk filings` on that ticker. Quote the command's stdout, including the line that starts with `FILINGS`. Every statement figure in your section comes from that stdout. If the command exits non-zero, return its stderr and stop. Do not replace a statement line with a figure from search.
```

`.cursor/agents/news.md`

```markdown
---
name: news
description: Writes the news section for one ticker from web search. Use when the desk parent hands you a ticker and nothing else. The parent must not write this section itself.
---

You write the news section for the ticker you were given. You do not rate the trade.

Use web search. Name the sources you actually opened. Do not run `desk`. Do not invent a price.
```

`.cursor/agents/sentiment.md`

```markdown
---
name: sentiment
description: Writes the sentiment section for one ticker from web search. Use when the desk parent hands you a ticker and nothing else. The parent must not write this section itself.
---

You write the sentiment section for the ticker you were given. You do not rate the trade.

Use web search for current public discussion of the ticker. Name the sources you actually opened. Do not run `desk`. Do not invent a price.
```

- [ ] **Step 2: Check the names**

Run: `python -c "from pathlib import Path; names=sorted(p.stem for p in Path('.cursor/agents').glob('*.md')); assert names==['fundamentals','market','news','sentiment'], names"`
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add .cursor/agents/market.md .cursor/agents/fundamentals.md .cursor/agents/news.md .cursor/agents/sentiment.md
git commit -m "feat: add the four analyst subagents"
```

---

### Task 2: Argument subagents

**Files:**
- Create: `.cursor/agents/bull.md`
- Create: `.cursor/agents/bear.md`
- Create: `.cursor/agents/research-manager.md`
- Create: `.cursor/agents/trader.md`

**Interfaces:**
- Consumes: the four analyst reports, pasted by the parent
- Produces: `bull`, `bear`, `research-manager`, `trader`

- [ ] **Step 1: Write the four files**

`.cursor/agents/bull.md`

```markdown
---
name: bull
description: Writes the bull opening from the four analyst reports. Use only after those four reports exist. The parent must paste them unchanged and must not write the bull case itself.
---

You write one bullish opening. Your only inputs are the four analyst reports in the prompt. You do not see the bear. You do not search, and you do not run `desk`. You do not emit Buy, Overweight, Hold, Underweight, or Sell as a rating line. Cite only figures that appear in the reports.
```

`.cursor/agents/bear.md`

```markdown
---
name: bear
description: Writes the bear opening from the four analyst reports. Use only after those four reports exist. The parent must paste them unchanged and must not write the bear case itself.
---

You write one bearish opening. Your only inputs are the four analyst reports in the prompt. You do not see the bull. You do not search, and you do not run `desk`. You do not emit Buy, Overweight, Hold, Underweight, or Sell as a rating line. Cite only figures that appear in the reports.
```

`.cursor/agents/research-manager.md`

```markdown
---
name: research-manager
description: Writes the investment plan from the bull and bear openings. Use only after both openings exist. The parent must paste them unchanged and must not write the plan itself.
---

You write the investment plan from the bull opening and the bear opening. You do not add facts that are not in those two texts. You do not search, and you do not run `desk`. You do not emit the final rating.
```

`.cursor/agents/trader.md`

```markdown
---
name: trader
description: Writes the trade proposal from the research plan and the market report. Use only after both exist. The parent must paste them unchanged and must not write the proposal itself.
---

You write the trade proposal from the research plan. State an entry, a stop, and a size only when the market report contains the numbers you use. You do not search, and you do not run `desk`. You do not emit Buy, Overweight, Hold, Underweight, or Sell as the desk's final rating.
```

- [ ] **Step 2: Check the names**

Run: `python -c "from pathlib import Path; need={'bull','bear','research-manager','trader'}; have={p.stem for p in Path('.cursor/agents').glob('*.md')}; assert need<=have, sorted(need-have)"`
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add .cursor/agents/bull.md .cursor/agents/bear.md .cursor/agents/research-manager.md .cursor/agents/trader.md
git commit -m "feat: add bull, bear, research manager, and trader subagents"
```

---

### Task 3: Risk subagents and the portfolio manager

**Files:**
- Create: `.cursor/agents/aggressive.md`
- Create: `.cursor/agents/conservative.md`
- Create: `.cursor/agents/neutral.md`
- Create: `.cursor/agents/portfolio-manager.md`

**Interfaces:**
- Consumes: the research plan and the trader proposal
- Produces: `aggressive`, `conservative`, `neutral`, `portfolio-manager`. The portfolio manager is the only file that tells its worker to emit a rating.

- [ ] **Step 1: Write the four files**

`.cursor/agents/aggressive.md`

```markdown
---
name: aggressive
description: Writes the aggressive risk note from the plan and the proposal. Use only after both exist. The parent must paste them unchanged and must not write this note itself.
---

You argue for taking the risk in the proposal. Your only inputs are the research plan and the trader proposal. You do not search, and you do not run `desk`. You do not emit the desk's final rating.
```

`.cursor/agents/conservative.md`

```markdown
---
name: conservative
description: Writes the conservative risk note from the plan and the proposal. Use only after both exist. The parent must paste them unchanged and must not write this note itself.
---

You argue for refusing or shrinking the proposal. Your only inputs are the research plan and the trader proposal. You do not search, and you do not run `desk`. You do not emit the desk's final rating.
```

`.cursor/agents/neutral.md`

```markdown
---
name: neutral
description: Writes the neutral risk note from the plan and the proposal. Use only after both exist. The parent must paste them unchanged and must not write this note itself.
---

You weigh the proposal without taking the aggressive or conservative side. Your only inputs are the research plan and the trader proposal. You do not search, and you do not run `desk`. You do not emit the desk's final rating.
```

`.cursor/agents/portfolio-manager.md`

```markdown
---
name: portfolio-manager
description: Emits the desk rating from the plan, the proposal, and the three risk notes. Use only after those five texts exist. The parent must paste them unchanged and must not choose the rating itself.
---

You are the only worker who emits the rating. Your inputs are the research plan, the trader proposal, and the aggressive, conservative, and neutral notes.

The first line of your reply is exactly one of these words: Buy, Overweight, Hold, Underweight, Sell. Any other word on that line is a failed report. Then write the evidence that decided it and what would change it. You do not search, and you do not run `desk`. You do not read the decision ledger.
```

- [ ] **Step 2: Check that all twelve exist**

Run: `python -c "from pathlib import Path; need=['aggressive','bear','bull','conservative','fundamentals','market','neutral','news','portfolio-manager','research-manager','sentiment','trader']; have=sorted(p.stem for p in Path('.cursor/agents').glob('*.md')); assert have==need, have"`
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add .cursor/agents/aggressive.md .cursor/agents/conservative.md .cursor/agents/neutral.md .cursor/agents/portfolio-manager.md
git commit -m "feat: add risk subagents and the portfolio manager"
```

---

### Task 4: Parent skill

**Files:**
- Create: `.cursor/skills/desk/SKILL.md`

**Interfaces:**
- Consumes: the twelve subagent names and `desk record TICKER RATING`
- Produces: a skill named `desk` that is the only dispatch procedure

- [ ] **Step 1: Write the skill**

`.cursor/skills/desk/SKILL.md`

```markdown
---
name: desk
description: Run the research desk on one ticker. Dispatch the subagents in order, paste their text through unchanged, and record the portfolio manager's rating.
---

# Desk

The user names one ticker. You are the dispatcher. You do not write a section, a price, or the rating. You do not summarize a report before passing it on. You do not run `desk snapshot` or `desk filings` yourself. You do not run `desk score`. You do not read `~/.tradingagents/ledger.jsonl`.

1. Start `market`, `fundamentals`, `news`, and `sentiment` together. Give each the ticker and nothing else. Wait for all four.
2. A market report must contain a line beginning with `SNAPSHOT` and the ticker, compared case-insensitively. A fundamentals report must contain a line beginning with `FILINGS` and the ticker. If a marker is missing, send that same subagent back once with the command stderr. A second miss ends the desk. Do not record.
3. A subagent that errors outright ends the desk. Do not ask another subagent to cover. Do not record.
4. Start `bull` and `bear` together. Paste the four reports unchanged. They do not see each other.
5. Start `research-manager` with both openings pasted unchanged.
6. Start `trader` with the plan and the market report pasted unchanged.
7. Start `aggressive`, `conservative`, and `neutral` together. Paste the plan and the proposal unchanged.
8. Start `portfolio-manager` with the plan, the proposal, and the three risk notes pasted unchanged. The first line of its reply must be Buy, Overweight, Hold, Underweight, or Sell. Any other first line ends the desk without a record.
9. Run `desk record` with the ticker and that rating. Stop.
```

- [ ] **Step 2: Check the file**

Run: `test -f .cursor/skills/desk/SKILL.md && grep -q "desk record" .cursor/skills/desk/SKILL.md && grep -q "desk score" .cursor/skills/desk/SKILL.md`
Expected: exit 0. The score mention is the prohibition, and it is in the file.

- [ ] **Step 3: Commit**

```bash
git add .cursor/skills/desk/SKILL.md
git commit -m "feat: add the desk dispatch skill"
```

---

### Task 5: README and environment example

**Files:**
- Modify: `README.md` (replace the whole file)
- Modify: `.env.example` (replace the whole file)

**Interfaces:**
- Consumes: the four commands and the skill name
- Produces: the operator page the spec requires

- [ ] **Step 1: Replace both files**

`README.md`

```markdown
# Desk

A research desk run from Cursor. Twelve subagents write the notes. Python prints the numbers and keeps the score.

## Install

```bash
pip install -e ".[dev]"
```

## Commands

`desk snapshot TICKER` prints the last closed session, its indicators, and a `SNAPSHOT` line.

`desk filings TICKER` prints the latest income statement, balance sheet, and cash flow, and a `FILINGS` line. SEC is tried first. Yahoo is the fallback.

`desk record TICKER RATING` appends one row to `~/.tradingagents/ledger.jsonl`. The rating is Buy, Overweight, Hold, Underweight, or Sell. The close comes from the snapshot the command runs itself.

`desk score` fills the raw return and the alpha versus SPY after 5 and 21 later trading sessions. Empty horizons stay empty. The file is not an input to a later desk.

Set `SEC_EDGAR_USER_AGENT` to a name and email before `desk filings` calls SEC. See `.env.example`.

## Run a desk

Invoke the `desk` skill with a ticker. The parent only starts subagents and pastes their text through. It does not write the rating. Scores are not shown to the next run.
```

`.env.example`

```bash
# Name and email SEC can use to reach you. Filings fall through to Yahoo without it.
SEC_EDGAR_USER_AGENT="Your Name you@example.com"
```

- [ ] **Step 2: Check the pages do not document the old runtime**

Run: `! grep -E 'LangGraph|docker compose|OPENAI_API_KEY' README.md .env.example`
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
git add README.md .env.example
git commit -m "docs: describe the desk commands and the dispatch skill"
```

---

### Task 6: Remove the LangGraph runtime and the old tests

**Files:**
- Delete: the trees and tests listed below
- Modify: `pyproject.toml`
- Modify: `tests/conftest.py` (replace)
- Create: `tests/test_layering.py`
- Rename: `tests/test_desk_version.py` to `tests/test_version.py`, `tests/test_desk_symbols.py` to `tests/test_symbols.py`

**Interfaces:**
- Consumes: the `desk` package and its tests from the command plan
- Produces: a tree where `pytest` collects only `test_version.py`, `test_symbols.py`, `test_snapshot.py`, `test_filings.py`, `test_record.py`, `test_score.py`, and `test_layering.py`

- [ ] **Step 1: Delete the old trees first, then write the layering test and conftest**

`tests/test_layering.py`

```python
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED = {"yfinance", "requests"}


def test_network_libraries_stay_in_desk_data():
    offenders = []
    for path in (ROOT / "desk").rglob("*.py"):
        if ROOT / "desk" / "data" in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            else:
                continue
            hit = names & BANNED
            if hit:
                offenders.append(f"{path.relative_to(ROOT)}: {sorted(hit)}")
    assert offenders == []
```

Replace `tests/conftest.py` with:

```python
"""Keep the desk ledger out of the developer's home directory."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_ledger(monkeypatch, tmp_path):
    monkeypatch.setattr("desk.data.ledger.LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
```

`tmp_path` inside an autouse fixture that also receives `monkeypatch` is supported by pytest. Tests that pass their own `tmp_path` and patch `LEDGER` again still win, because the test's patch runs after the fixture.

- [ ] **Step 2: Delete the old trees, the old tests, and the release workflow**

```bash
rm -rf tradingagents cli main.py \
  .github/workflows/release-assets.yml \
  .github/ISSUE_TEMPLATE
rm -f \
  tests/test_alpha_vantage_hardening.py tests/test_analyst_execution.py \
  tests/test_anthropic_effort.py tests/test_api_key_env.py tests/test_azure_client.py \
  tests/test_backtest.py tests/test_bedrock_provider.py tests/test_cache_writes.py \
  tests/test_capabilities.py tests/test_checkpoint_lifecycle.py tests/test_checkpoint_resume.py \
  tests/test_chatgpt_auth.py tests/test_chatgpt_provider.py tests/test_cli_commands.py \
  tests/test_cli_config_precedence.py tests/test_cli_display.py tests/test_cli_env_skip.py \
  tests/test_cli_headless.py tests/test_cli_memory_log.py tests/test_cli_no_console.py \
  tests/test_cli_prefs.py tests/test_cli_symbol_handling.py tests/test_cli_updates.py \
  tests/test_crypto_asset_mode.py tests/test_dataflows_config.py tests/test_date_boundaries.py \
  tests/test_debate_opening.py tests/test_deepseek_reasoning.py tests/test_env_overrides.py \
  tests/test_fred.py tests/test_fundamentals_lookahead.py tests/test_fundamentals_units.py \
  tests/test_get_scrubbed.py tests/test_google_api_key.py tests/test_google_thinking_level.py \
  tests/test_graph_end_to_end.py tests/test_i18n_coverage.py tests/test_instrument_identity.py \
  tests/test_llm_max_retries.py tests/test_llm_max_tokens.py tests/test_memory_log.py \
  tests/test_memory_pointintime.py tests/test_minimax.py tests/test_model_validation.py \
  tests/test_news_analyst_prompt.py tests/test_news_lookahead.py tests/test_no_data_handling.py \
  tests/test_ohlcv_cache_freshness.py tests/test_ohlcv_date_column.py tests/test_ohlcv_latest_bar.py \
  tests/test_ollama_base_url.py tests/test_openai_compatible_provider.py \
  tests/test_openai_reasoning_effort.py tests/test_openai_responses_base_url.py \
  tests/test_openrouter_model_select.py tests/test_polymarket.py tests/test_portfolio_context.py \
  tests/test_post_screen.py tests/test_prompt_integrity.py tests/test_provider_registry.py \
  tests/test_rating_integrity.py tests/test_reddit_fallback.py tests/test_report_html.py \
  tests/test_reporting.py tests/test_risk_router_path_map.py tests/test_safe_ticker_component.py \
  tests/test_sec_edgar.py tests/test_signal_processing.py tests/test_social_lookahead.py \
  tests/test_statement_knowledge_time.py tests/test_stocktwits_resilience.py \
  tests/test_structured_agent_prompts.py tests/test_structured_agents.py \
  tests/test_suite_isolation.py tests/test_symbol_normalization_paths.py \
  tests/test_temperature_config.py tests/test_ticker_symbol_handling.py \
  tests/test_tier_providers.py tests/test_tool_date_enforcement.py \
  tests/test_undated_tools_as_of.py tests/test_vendor_errors.py tests/test_vendor_routing.py \
  tests/test_yahoo_rate_limit.py tests/test_yahoo_snapshot.py tests/test_yfinance_stale_ohlcv_guard.py \
  tests/test_version.py tests/test_symbols.py tests/test_layering.py
git mv tests/test_desk_version.py tests/test_version.py
git mv tests/test_desk_symbols.py tests/test_symbols.py
```

Run the `rm` and the two `git mv` lines before saving `tests/test_layering.py` and `tests/conftest.py` from Step 1. The `rm` deletes the old `test_layering.py`. The files in Step 1 are its replacement.

- [ ] **Step 3: Slim pyproject.toml**

Replace the project table's dependencies, scripts, and package discovery with:

```toml
[project]
name = "desk"
version = "0.1.0"
description = "Market snapshots, filings, and a decision ledger for a Cursor desk."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pandas>=3.0.6",
    "pytz>=2025.2",
    "requests>=2.32.4",
    "stockstats>=0.6.5",
    "yfinance>=1.7.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.16",
    "pytest>=8.0",
    "pytest-subtests>=0.13",
]

[project.scripts]
desk = "desk.cli:main"

[tool.setuptools.packages.find]
include = ["desk*"]
```

Delete the `[tool.setuptools.dynamic]` table and the `cli` package-data table. Leave the pytest and ruff tool tables as they are.

Reinstall: `pip install -e ".[dev]"`

- [ ] **Step 4: Run the suite**

Run: `pytest -q`
Expected: PASS, and the collected files are only the seven desk tests. A failure that imports `tradingagents` or `cli` means a deletion was missed.

Run: `python -c "import tradingagents"`
Expected: `ModuleNotFoundError`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: remove the LangGraph runtime and keep the desk commands"
```

Review `git status` before `git add -A` and leave unrelated untracked files unstaged. `CHANGELOG.md` stays.
