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
