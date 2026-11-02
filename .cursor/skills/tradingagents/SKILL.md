---
name: tradingagents
description: Run TradingAgents on one ticker. Dispatch the subagents in order, pass deliverable paths only, and record the portfolio manager's rating from rating.md.
---

# TradingAgents

## For the user

For a full run with analysts and risk notes in parallel, start in the Agents window with **`/multitask`** before you name the ticker. Plain Agent mode works for day-to-day runs; parallel workers are configured to run in the background so the dispatcher is not blocked on each one sequentially.

The user names one ticker. You are the dispatcher. You do not write a section, a price, or the rating. You do not paste, quote, or summarize a deliverable into the next subagent. If a reply contains a report body, ignore the body and use the file. You do not run `tradingagents snapshot` or `tradingagents filings` yourself. You do not run `tradingagents score`. You do not read `~/.tradingagents/ledger.jsonl`.

## Run directory

Before step 1, run `tradingagents run-dir TICKER` with the user's ticker. Stdout is one line: the absolute path to an empty run directory (`.tradingagents/<TICKER>/<local-date>/` under the current working directory). Exit non-zero stops the run. All deliverable paths below are files in that directory.

## Dispatch

**Parallel batches.** When a step says "together", use **one assistant turn** with **one Task call per subagent in that batch** (step 1: four Task calls in the same turn, not four turns). Cursor runs Tasks issued in the same turn concurrently. Do not begin the next numbered step until every deliverable file from that batch exists (or the batch has failed outright). If the user started with `/multitask`, set `run_in_background: true` on every Task.

1. Start `market`, `fundamentals`, `news`, and `sentiment` together. Give each the ticker, its output path (`market.md`, `fundamentals.md`, `news.md`, `sentiment.md`), and nothing else. Wait for all four. A successful reply is the output path only. Command failure is stderr in the reply and no deliverable file.
2. Read `market.md` and `fundamentals.md`. `market.md` must contain a line beginning with `SNAPSHOT` and the ticker, compared case-insensitively. `fundamentals.md` must contain a line beginning with `FILINGS` and the ticker. If a marker is missing, send that same subagent back once with the command stderr. A second miss ends the run. Do not record.
3. A subagent that errors outright ends the run. Do not ask another subagent to cover. Do not record.
4. Start `bull` and `bear` together. Pass the four analyst paths only. Outputs `bull.md` and `bear.md`. Do not give either the other's path.
5. Start `research-manager` with `bull.md` and `bear.md`. Output `plan.md`.
6. Start `trader` with `plan.md` and `market.md`. Output `proposal.md`.
7. Start `aggressive`, `conservative`, and `neutral` together. Pass `plan.md` and `proposal.md` to each. Outputs `aggressive.md`, `conservative.md`, `neutral.md`.
8. Start `portfolio-manager` with `plan.md`, `proposal.md`, `aggressive.md`, `conservative.md`, and `neutral.md`. Output `rating.md`. Read the first line of `rating.md`. It must be exactly one of Buy, Overweight, Hold, Underweight, or Sell. Any other first line ends the run without a record. The chat reply is not the rating.
9. Run `tradingagents record` with the ticker and that rating. Tell the user the rating and the run directory path. Do not recap the debate. Stop.
