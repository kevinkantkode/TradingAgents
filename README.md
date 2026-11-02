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
