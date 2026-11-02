# TradingAgents

A research run from Cursor. Twelve subagents write the notes. Python prints the numbers and keeps the score.

## Install

```bash
pip install -e ".[dev]"
```

## Commands

`tradingagents run-dir TICKER` creates an empty `.tradingagents/<TICKER>/<local-date>/` run folder and prints its absolute path. A same-day rerun wipes that folder first.

`tradingagents snapshot TICKER` prints the last closed session, its indicators, and a `SNAPSHOT` line.

`tradingagents filings TICKER` prints Yahoo's quarterly income statement, balance sheet, and cash flow, the four most recent columns of each, and insider transactions when Yahoo has them. An annual column is included when its period is not already in the quarters. The same output includes the latest SEC revenue, assets, and operating-cash-flow figures when the company files. SEC replaces the statements only when Yahoo has none. The first line is `FILINGS`.

`tradingagents record TICKER RATING` appends one row to `~/.tradingagents/ledger.jsonl`. The rating is Buy, Overweight, Hold, Underweight, or Sell. The close comes from the snapshot the command runs itself.

`tradingagents score` fills the raw return and the alpha versus SPY after 5 and 21 later trading sessions. Empty horizons stay empty. The file is not an input to a later run.

Set `SEC_EDGAR_USER_AGENT` to a name and email before `tradingagents filings` calls SEC. See `.env.example`.

## Run

Invoke the `tradingagents` skill with a ticker. The parent only starts subagents and passes deliverable paths under `.tradingagents/<TICKER>/<date>/`. It does not write the rating. Scores are not shown to the next run.
