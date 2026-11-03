---
name: fetch-tradingagents
description: Download a successful TradingAgents GitHub Actions artifact into .tradingagents/<TICKER>/<date>/. Use only when the user invokes /fetch-tradingagents. An optional run id selects that run. With no run id, take the latest successful run.
disable-model-invocation: true
---

# Fetch TradingAgents

Run `scripts/fetch-tradingagents.sh` from the repo root.

The only input is an optional GitHub Actions run id. If the user gave one, pass it. If they did not, run the script with no arguments. That takes the latest successful run of `tradingagents.yml`.

The ticker is not an input. It is inside the artifact, as `.tradingagents/<TICKER>/<date>/`.

Do not dispatch a workflow. Do not follow the order skill. Do not call a broker. Reply with the script's rating line and path.
