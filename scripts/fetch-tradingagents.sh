#!/usr/bin/env bash
# Download a successful Actions run into .tradingagents/<TICKER>/<date>/.
# Pass a run id to fetch that run. Other tickers already there are left in place.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

run_id="${1:-}"
if [[ -z "$run_id" ]]; then
  run_id="$(gh run list --workflow tradingagents.yml --status success --limit 1 --json databaseId --jq '.[0].databaseId')"
fi
if [[ -z "$run_id" || "$run_id" == "null" ]]; then
  echo "no successful tradingagents run" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
gh run download "$run_id" --name tradingagents --dir "$tmp"

rating="$(find "$tmp" -name rating.md -type f | sort | head -n 1)"
if [[ -z "$rating" ]]; then
  echo "artifact has no rating.md" >&2
  exit 1
fi

mkdir -p .tradingagents
cp -a "$tmp/." .tradingagents/
rel=".tradingagents/${rating#"$tmp/"}"
echo "$(head -n 1 "$rating") ${rel}"
