# Cursor desk

A research desk run from Cursor. Twelve subagents do the talking. A parent agent only starts them, pastes their text through unchanged, and checks two markers. Python prints prices, statements, and a score. It does not call a model.

This replaces the LangGraph runtime. The old package is not kept beside the new one.

## What this is for

The user names a ticker. Separate subagents write a market note, a fundamentals note, a news note, and a sentiment note. A bull and a bear each argue from those four notes without seeing each other. A research manager writes a plan. A trader writes a proposal. Three risk subagents answer the proposal. A portfolio manager emits one rating. Python records that rating against the last completed close, and later fills in what the price did after 5 and 21 trading days.

The rating is a note. Nothing in this system places an order.

A later price does not revise the note. A gain after a week and a loss after a month are both stored. Neither is shown to the next desk, and no model is asked to explain them.

## Out of scope

- Robinhood, any broker, and any MCP server.
- Running the desk as of a past date, look-ahead filters, and the backtest grid.
- News, social, FRED, and Polymarket clients. Those subagents use Cursor web search.
- Feeding a score, a reflection, or a past rating into a later run.
- An HTML report. The note is the subagent text in the Cursor session.
- A compatibility shim for `tradingagents`, `TradingAgentsGraph`, or the `tradingagents` console script.

## Desk

Workers are project subagents in `.cursor/agents/`. Each file is markdown with `name` and `description` frontmatter. The body is that worker's instructions. The description says when the parent may delegate to it, and that the parent must not answer in its place. No file sets a model.

The parent procedure is `.cursor/skills/desk/SKILL.md`. Invoking the skill on a ticker is the run. The skill is a dispatch list. It does not contain a view of any market.

### Order

The four analysts start together. The parent waits for all four.

| Subagent | Inputs | Must include | Must not |
|---|---|---|---|
| `market` | Ticker | The `SNAPSHOT` line and the table from `desk snapshot` | Rate the trade, search for a price, type a close that is not in the table |
| `fundamentals` | Ticker | The `FILINGS` line and the tables from `desk filings` | Rate the trade, substitute a searched figure for a statement line |
| `news` | Ticker | Sources it actually opened | Call `desk`, invent a price, rate the trade |
| `sentiment` | Ticker | Sources it actually opened | Call `desk`, invent a price, rate the trade |

Bull and bear then start together. Each receives the four reports verbatim and nothing else. They do not see each other. One opening each. There is no rebuttal round.

`research-manager` receives both openings and writes the plan. `trader` receives the plan and writes the proposal, including entry, stop, and size only when it can state them from the market report. `aggressive`, `conservative`, and `neutral` start together. Each receives the plan and the proposal. `portfolio-manager` receives the plan, the proposal, and the three risk notes. It is the only subagent allowed to emit a rating, and the rating is one of Buy, Overweight, Hold, Underweight, Sell, on its own line, spelled that way.

### What the parent may do

- Start the subagent named for the current step.
- Paste the previous artifact unchanged.
- Check that a market report contains the `SNAPSHOT <TICKER>` line and a fundamentals report contains the `FILINGS <TICKER>` line. Ticker is compared case-insensitively.
- On a missing marker, send that same subagent back once, with the command's stderr. A second miss ends the desk.
- After a valid portfolio-manager rating, run `desk record <TICKER> <RATING>`.

### What the parent must not do

- Summarize a report before passing it on.
- Write or edit a section, a price, or the rating.
- Run `desk snapshot` or `desk filings` itself to fill a hole.
- Ask a different subagent to cover a failed one.
- Run `desk record` when any required report is missing or the rating is not one of the five words.
- Run `desk score`, or paste a ledger row into any subagent.

A subagent that errors outright ends the desk. Nothing is recorded.

## Commands

The console script is `desk`, implemented with the standard-library argument parser. Four subcommands. Success prints to stdout and exits 0. Failure prints the reason to stderr, prints no success marker, and exits 1.

Every ticker is passed through `normalize_symbol` before a request. `XAUUSD+` resolves to `GC=F`, `0700.HK` to `0700.HK`, `600519.SH` to `600519.SS`. A ticker that fails `safe_ticker_component` is rejected before any network call.

### `desk snapshot TICKER`

Downloads daily OHLCV and computes a fixed indicator set in process: `close_10_ema`, `close_50_sma`, `close_200_sma`, `rsi`, `boll`, `boll_ub`, `boll_lb`, `macd`, `macds`, `macdh`, `atr`. One indicator that cannot be computed is printed `N/A` with the exception type. That does not fail the command. No rows at all does.

The anchor bar is the last fully closed session, in that listing's exchange timezone. The session still trading is excluded, even when Yahoo has already printed a partial bar for today. The same rule applies when `record` takes the close, so the quoted close and the stored close are the same bar as long as a new session has not completed in between.

Stdout begins with one machine line, then the human table:

```text
SNAPSHOT NVDA 2026-11-02 187.25
```

`SNAPSHOT`, the canonical ticker, the anchor date `YYYY-MM-DD`, and the close as printed in the table. The table has the latest OHLCV row, the indicator values on that row, and the recent closes (up to 30). Rows after the anchor date are absent.

Exit 1 when the vendor returns no usable rows, or the request fails. No `SNAPSHOT` line in that case.

### `desk filings TICKER`

Prints the income statement, the balance sheet, and the cash flow. Yahoo supplies the line items: the four most recent quarterly columns, plus an annual column when that period is not already among the quarters. Insider transactions from the same Yahoo ticker are printed after the statements when that table is non-empty. This is whatever is reported today. It does not reconstruct what was public on an older date.

When Yahoo has statements, the latest SEC revenue, assets, and operating-cash-flow figures are printed under those tables. They do not replace the tables. SEC company facts replace the statements only when Yahoo has none. A SEC request failure leaves the Yahoo tables in place and records the failure in the output. Stdout begins with one marker line:

```text
FILINGS NVDA quarterly sec
FILINGS NVDA quarterly yahoo
FILINGS NVDA annual sec
FILINGS NVDA annual yahoo
```

Those four are the only marker lines. The marker says `quarterly` when a quarterly statement is printed, and `annual` when only the annual statement is. `yahoo` is the source when Yahoo supplied the tables. `sec` is the source only for the fallback. Exit 1 only when both sources produce no statement. No `FILINGS` line in that case.

Figures are printed with their units. A percent stays a percent. A ratio stays a ratio. Currency is the figure's own currency, including minor units such as GBp labeled as such rather than divided in secret.

SEC requests send `SEC_EDGAR_USER_AGENT` when set, otherwise `desk/<version> (contact@example.com)`.

### `desk record TICKER RATING`

Appends one JSON object as a line to `~/.tradingagents/ledger.jsonl`, creating the directory if needed. The write is atomic: a temp file beside the ledger, then replace. A failed write leaves the previous ledger intact.

`RATING` must be one of the five words, matched case-insensitively and stored in the canonical spelling. Anything else exits 1 and does not create or modify the file.

The command takes no close. It runs the snapshot itself and stores that anchor date and close. If the snapshot exits 1, `record` exits 1 and writes no row.

Two records for the same ticker on the same day are two rows.

The object:

| Field | Value |
|---|---|
| `id` | New UUID |
| `decided_at` | UTC timestamp, ISO-8601 |
| `ticker` | Canonical symbol |
| `rating` | One of the five words |
| `anchor_date` | `YYYY-MM-DD` of the anchor bar |
| `anchor_close` | That bar's close, as a JSON number |
| `benchmark` | `SPY` |
| `ret_5`, `alpha_5`, `exit_date_5` | `null` |
| `ret_21`, `alpha_21`, `exit_date_21` | `null` |

Stdout is that object, pretty-printed. The command does not store the debate.

### `desk score`

Reads the ledger and fills empty horizons whose window has since traded. It writes the file back atomically. It prints one line per row it touched, and a line per row it skipped, to stdout. It writes no prose and it does not call a model.

A horizon of N trading days is the close of the Nth fully closed session of that instrument strictly after `anchor_date`. The anchor bar is not day 1. Five means five later sessions.

`ret_N` is `(exit_close / anchor_close) - 1`, stored as a fraction. `exit_date_N` is that session's date.

`alpha_N` is `ret_N` minus SPY's return over the same calendar span: SPY's last fully closed close on or before `anchor_date`, to SPY's last fully closed close on or before `exit_date_N`. SPY is not currency-hedged. A listing in another currency is still subtracted from SPY's percent return. If SPY has no close on or before one of those dates, `ret_N` and `exit_date_N` are still written and `alpha_N` stays `null`.

A horizon whose Nth later session does not exist yet is left `null`. The command still exits 0.

A horizon that is due, but whose prices cannot be fetched, stays `null`. The ticker, the horizon, and the reason go to stderr. If any due horizon fails this way, the command exits 1 after scoring the rows it could. It never writes `0` for a missing price.

Running `score` twice does not change a field that is already a number.

## Package

The installable project is `desk` at version `0.1.0`. `pyproject.toml` names the script `desk = desk.cli:main`. The description says it prints market snapshots, filings, and a decision ledger for a Cursor desk.

Runtime dependencies are `pandas`, `yfinance`, `stockstats`, `requests`, and `pytz`. Dev dependencies stay `pytest`, `pytest-subtests`, and `ruff`.

Removed from the dependency list: `langchain-core`, `langchain-anthropic`, `langchain-google-genai`, `langchain-openai`, `langgraph`, `langgraph-checkpoint-sqlite`, `cryptography`, `markdown-it-py`, `packaging`, `python-dotenv`, `questionary`, `rich`, `typer`, `typing-extensions`, and the `bedrock` extra (`langchain-aws`).

`.env.example` keeps `SEC_EDGAR_USER_AGENT` and drops the model-provider keys, the update-check flag, and the path overrides for the old results, cache, and memory log. The ledger path is not configurable in this version.

`README.md` is replaced. It states the install (`pip install -e ".[dev]"`), the four commands, the ledger path, the skill to invoke, the rule that the parent only routes, and that scores are not an input to a later run. It does not document LangGraph, Docker, or a model provider.

## What is deleted

These trees and modules go. Their tests go with them. Nothing re-imports them.

- `tradingagents/graph/`
- `tradingagents/agents/`
- `tradingagents/llm_clients/`
- `tradingagents/memory/`
- `cli/`
- `tradingagents/backtest.py`
- `tradingagents/reporting.py`
- `tradingagents/report_html.py`
- `tradingagents/portfolio.py`
- `tradingagents/default_config.py`
- `main.py`

Inside `tradingagents/dataflows/`, delete the vendors and helpers that no command calls:

- `vendors/alpha_vantage/`
- `vendors/fred.py`
- `vendors/polymarket.py`
- `vendors/reddit.py`
- `vendors/stocktwits.py`
- `vendors/yahoo/news.py`
- `date_window.py`. The desk does not withhold or clamp by a historical trade date.
- `router.py`. Snapshot and filings call their vendors directly.
- `config.py`. Nothing reads `DEFAULT_CONFIG`.

Surviving data code moves under `desk/data/` and is imported as `desk`. The `tradingagents` package is removed, including `tradingagents/__init__.py`. Callers do not keep the old import paths.

Code that moves, after the historical branches are cut out:

- Symbol normalization and `safe_ticker_component`.
- Yahoo OHLCV load, the stale-bar and gap behavior the snapshot needs, and `build_verified_market_snapshot`, changed so the anchor bar is the last fully closed session.
- Yahoo statement fetch used as the filings fallback, without the past-date withhold.
- The SEC fetch used for the latest quarter, without as-filed vintage reconstruction.
- Vendor error types those two fetches still raise (`NoMarketDataError`, `VendorUnavailableError`).
- SEC errors that include response text redact `SEC_EDGAR_USER_AGENT` before the text is printed or raised. One test feeds a body containing the agent string and asserts the output does not.

`CHANGELOG.md` stays as the upstream history. It is not rewritten to pretend those releases were this desk.

`.github/workflows/ci.yml` still runs `pytest`. `.github/workflows/release-assets.yml` is deleted. It builds a wheel for the old package and attaches it to a GitHub release. Issue templates that describe the old CLI, providers, and Docker are deleted rather than rewritten. There is no public issue workflow in this design.

## Tests

No existing test file is kept as it is. A behavior that still exists is specified again in a new test. A behavior that belonged to the deleted runtime is not retested.

The suite calls the commands with fixtures. No test hits Yahoo, SEC, or a Cursor subagent. `conftest.py` is rewritten so the ledger path for the run is a temporary directory, and so a developer's environment cannot change a command's output. The old `TRADINGAGENTS_*` blanking overlay is deleted with the config it protected.

### New tests

`tests/test_snapshot.py`

- A fixture series yields a `SNAPSHOT` line whose ticker, date, and close are the last fully closed row.
- A partial bar dated today, in the exchange timezone, is not that row.
- The close on the marker line equals the close in the table.
- An empty series exits 1 and prints no `SNAPSHOT` line.
- `XAUUSD+` is requested from the vendor as `GC=F`.
- A ticker that fails `safe_ticker_component` exits 1 before the vendor is called.

`tests/test_filings.py`

- An SEC fixture prints `FILINGS <TICKER> quarterly sec` and the three statements.
- An SEC failure and a Yahoo quarterly fixture prints `FILINGS <TICKER> quarterly yahoo`.
- Empty quarterly frames and a non-empty annual fixture print `FILINGS <TICKER> annual yahoo` when Yahoo supplied them, or `annual sec` when SEC supplied them.
- Both sources empty exits 1 and prints no `FILINGS` line.
- An SEC error body that contains `SEC_EDGAR_USER_AGENT` is printed without that string.
- A past-date argument does not exist on the command. There is no test that withholds a statement because the run is historical.

`tests/test_record.py`

- `Hold` appends one object whose `anchor_close` is the fixture snapshot's close, not a number from argv.
- `buy` is stored as `Buy`.
- `REVIEW`, an empty rating, and a sixth word exit 1 and leave the file absent.
- A snapshot failure exits 1 and leaves the file absent.
- Two records for the same ticker are two lines.

`tests/test_score.py`

- A row whose instrument then has five later closes fills `ret_5`, `exit_date_5`, and `alpha_5` against a fixture SPY series. `ret_21` stays null. Exit 0.
- Twenty-one later closes fill both horizons. The 5-day fields already stored are not changed on the second run.
- Return is `(later / anchor) - 1` from the stored anchor close, not from the next session's close.
- A shorter series than the horizon leaves the field null and exits 0.
- A due horizon whose price fetch raises leaves that field null, prints the reason to stderr, and exits 1. A sibling row that can be scored is still written.
- SPY missing a covering close leaves `alpha_N` null and still writes `ret_N`.
- The command's output contains no reflection and no rating advice.

`tests/test_symbols.py`

- The alias, crypto, forex, Hong Kong padding, and Shanghai `.SH` to `.SS` cases that `normalize_symbol` already guarantees.
- `safe_ticker_component` rejects `..`, a slash, and an empty string.

### Existing files

Delete each of these. Do not edit them into the new tests. Where a surviving behavior is named, the new test above is the one that covers it.

| File | Disposition |
|---|---|
| `tests/conftest.py` | Rewrite as the temp ledger isolation described above. Delete the env overlay and the socket/API-key hang guards that existed for the model clients. |
| `tests/test_yahoo_snapshot.py` | Delete. Covered by `test_snapshot.py`. |
| `tests/test_ohlcv_date_column.py` | Delete. Keep only the date-column behavior snapshot still needs, retested in `test_snapshot.py`. |
| `tests/test_ohlcv_latest_bar.py` | Delete. The fully-closed-session rule is retested in `test_snapshot.py`. |
| `tests/test_ohlcv_cache_freshness.py` | Delete. This version does not cache OHLCV. No test reads `~/.tradingagents/cache`. |
| `tests/test_yfinance_stale_ohlcv_guard.py` | Delete. The fully-closed-session rule in `test_snapshot.py` is the bar the command will quote. A stale intraday printout is excluded by that rule. |
| `tests/test_yahoo_rate_limit.py` | Delete. This version does not add a retry loop. A failed request is the command's exit 1. |
| `tests/test_symbols.py` | Delete. Replaced by the new `test_symbols.py`. |
| `tests/test_safe_ticker_component.py` | Delete. Folded into `test_symbols.py`. |
| `tests/test_symbol_normalization_paths.py` | Delete. The commands normalize before the vendor call. That is asserted in `test_snapshot.py`. |
| `tests/test_ticker_symbol_handling.py` | Delete. CLI prompting is gone. |
| `tests/test_sec_edgar.py` | Delete. Latest-quarter behavior is retested in `test_filings.py`. As-filed vintage cases are not rewritten. |
| `tests/test_fundamentals_units.py` | Delete. Unit labeling is retested in `test_filings.py`. |
| `tests/test_fundamentals_lookahead.py` | Delete. No successor. |
| `tests/test_statement_knowledge_time.py` | Delete. No successor. |
| `tests/test_vendor_errors.py` | Delete. The no-rows and both-sources-failed exits cover the command boundary. |
| `tests/test_vendor_routing.py` | Delete. There is no vendor router. |
| `tests/test_no_data_handling.py` | Delete. Covered by the empty-series and empty-filings cases. |
| `tests/test_get_scrubbed.py` | Delete. The user-agent redaction case in `test_filings.py` replaces it. |
| `tests/test_version.py` | Delete. Replace with one assertion that `desk.__version__` is `0.1.0`. |
| `tests/test_layering.py` | Delete. Replace with one assertion that `yfinance` and `requests` are imported only under `desk/data/`. |
| `tests/test_suite_isolation.py` | Delete. The new conftest's temp ledger is the isolation guarantee, asserted by `test_record.py` writing only inside that directory. |

Delete with no successor. These cover the LangGraph runtime, the model clients, the interactive CLI, memory, the backtest, or a data source this desk does not call:

`test_alpha_vantage_hardening.py`, `test_analyst_execution.py`, `test_anthropic_effort.py`, `test_api_key_env.py`, `test_azure_client.py`, `test_backtest.py`, `test_bedrock_provider.py`, `test_cache_writes.py`, `test_capabilities.py`, `test_checkpoint_lifecycle.py`, `test_checkpoint_resume.py`, `test_chatgpt_auth.py`, `test_chatgpt_provider.py`, `test_cli_commands.py`, `test_cli_config_precedence.py`, `test_cli_display.py`, `test_cli_env_skip.py`, `test_cli_headless.py`, `test_cli_memory_log.py`, `test_cli_no_console.py`, `test_cli_prefs.py`, `test_cli_symbol_handling.py`, `test_cli_updates.py`, `test_crypto_asset_mode.py`, `test_dataflows_config.py`, `test_date_boundaries.py`, `test_debate_opening.py`, `test_deepseek_reasoning.py`, `test_env_overrides.py`, `test_fred.py`, `test_google_api_key.py`, `test_google_thinking_level.py`, `test_graph_end_to_end.py`, `test_i18n_coverage.py`, `test_instrument_identity.py`, `test_llm_max_retries.py`, `test_llm_max_tokens.py`, `test_memory_log.py`, `test_memory_pointintime.py`, `test_minimax.py`, `test_model_validation.py`, `test_news_analyst_prompt.py`, `test_news_lookahead.py`, `test_ollama_base_url.py`, `test_openai_compatible_provider.py`, `test_openai_reasoning_effort.py`, `test_openai_responses_base_url.py`, `test_openrouter_model_select.py`, `test_polymarket.py`, `test_portfolio_context.py`, `test_post_screen.py`, `test_prompt_integrity.py`, `test_provider_registry.py`, `test_rating_integrity.py`, `test_reddit_fallback.py`, `test_report_html.py`, `test_reporting.py`, `test_risk_router_path_map.py`, `test_signal_processing.py`, `test_social_lookahead.py`, `test_stocktwits_resilience.py`, `test_structured_agent_prompts.py`, `test_structured_agents.py`, `test_temperature_config.py`, `test_tier_providers.py`, `test_tool_date_enforcement.py`, `test_undated_tools_as_of.py`.

After the refactor, `pytest` collects only the new files. A leftover test that imports `tradingagents` or `cli` is a failed refactor, not a skipped test.

## Subagent files

Each file under `.cursor/agents/` states its inputs, the command it must run, the marker it must quote, and the actions forbidden in the table above. The market and fundamentals files include the exact command line. The news and sentiment files say web search is their source and `desk` is not. The portfolio-manager file lists the five ratings and says any other word is a failed report. None of the files tell the worker to read `~/.tradingagents/ledger.jsonl`.

`.cursor/skills/desk/SKILL.md` lists the order, the paste rule, the one retry, and the `desk record` call. It tells the parent to stop without recording when a second marker check fails.

## Done

A fresh install exposes `desk` and not `tradingagents`. `desk snapshot`, `desk filings`, `desk record`, and `desk score` behave as specified, under the new tests, with no network. The twelve subagent files and the skill are in the tree. The deleted modules and the deleted tests are gone. `pytest` passes.
