# Desk commands implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install a `desk` command that prints a price snapshot, the latest statements, and a decision ledger scored 5 and 21 trading days later, with no network in the tests.

**Architecture:** `desk` is a new package beside the old `tradingagents` tree. Commands call pure functions that accept fixture frames. Yahoo and SEC are reached only through two fetch functions the tests replace. This plan does not delete the old package. That happens in `docs/superpowers/plans/2026-11-02-cursor-desk.md` after these commands pass.

**Tech Stack:** Python 3.11+, argparse, pandas, stockstats, yfinance, requests, pytz, pytest.

## Global Constraints

- Package name `desk`, version `0.1.0`. Script `desk = desk.cli:main`.
- Do this work on a new branch named `desk`, cut from the current `HEAD`. Do not commit on `main`. Do not push.
- Runtime dependencies added for this package are only `pandas`, `yfinance`, `stockstats`, `requests`, and `pytz`. Do not remove the existing LangChain dependencies in this plan. The old test suite must still pass.
- Ratings stored as `Buy`, `Overweight`, `Hold`, `Underweight`, `Sell`.
- Ledger path `~/.tradingagents/ledger.jsonl`. Tests never write the real home ledger.
- Horizons are 5 and 21 trading sessions after the anchor date. The anchor bar is not day 1.
- Benchmark is `SPY`. Returns are fractions `(later / anchor) - 1`.
- `desk snapshot` first line is `SNAPSHOT <CANONICAL> <YYYY-MM-DD> <close>`.
- `desk filings` first line is one of `FILINGS <CANONICAL> quarterly sec`, `FILINGS <CANONICAL> quarterly yahoo`, `FILINGS <CANONICAL> annual sec`, `FILINGS <CANONICAL> annual yahoo`.
- Failure prints the reason to stderr, prints no success marker, and exits 1.
- No test hits Yahoo, SEC, or a Cursor subagent.
- The session still trading is excluded. Today's date in the listing's exchange timezone is not an anchor bar.

## File map

- `desk/__init__.py` — version.
- `desk/cli.py` — argparse and process exit codes.
- `desk/data/symbols.py` — copied ticker normalization.
- `desk/data/errors.py` — `DeskError`, `NoMarketDataError`, `VendorUnavailableError`.
- `desk/data/prices.py` — snapshot text and `fetch_daily`.
- `desk/data/filings.py` — filings text, SEC and Yahoo fetch, user-agent redaction.
- `desk/data/ledger.py` — append and score.
- `tests/test_version.py`, `tests/test_symbols.py`, `tests/test_snapshot.py`, `tests/test_filings.py`, `tests/test_record.py`, `tests/test_score.py` — new tests. Do not edit the existing files of those names. `tests/test_symbols.py` and `tests/test_version.py` already exist. This plan's symbol and version tests live in `tests/test_desk_symbols.py` and `tests/test_desk_version.py` so the old suite keeps collecting. Plan 2 deletes the old files and renames these to the spec names.

---

### Task 1: Package skeleton

**Files:**
- Create: `desk/__init__.py`
- Create: `desk/data/__init__.py`
- Create: `desk/cli.py`
- Create: `tests/test_desk_version.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing
- Produces: `desk.__version__ == "0.1.0"`. `desk.cli.main(argv: list[str] | None) -> int`.

- [ ] **Step 1: Write the failing test**

```python
def test_desk_version_is_0_1_0():
    import desk
    assert desk.__version__ == "0.1.0"
```

Save as `tests/test_desk_version.py`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_desk_version.py::test_desk_version_is_0_1_0 -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'desk'`

- [ ] **Step 3: Write the package and register it**

`desk/__init__.py`:

```python
"""Market snapshots, filings, and a decision ledger for a Cursor desk."""

__version__ = "0.1.0"
```

`desk/data/__init__.py` is an empty file.

`desk/cli.py`:

```python
"""The desk command. Subcommands arrive in later tasks."""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="desk")
    parser.add_subparsers(dest="command", required=True)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

In `pyproject.toml`, add `desk*` to the packages list and register the script. Leave `tradingagents = "cli.main:app"` in place.

```toml
[project.scripts]
tradingagents = "cli.main:app"
desk = "desk.cli:main"

[tool.setuptools.packages.find]
include = ["tradingagents*", "cli*", "desk*"]
```

The dynamic version attribute stays `tradingagents.__version__` until plan 2. `desk.__version__` is a literal.

Install the new package into the current environment: `pip install -e .`

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_desk_version.py::test_desk_version_is_0_1_0 -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git checkout -b desk
git add desk/__init__.py desk/data/__init__.py desk/cli.py tests/test_desk_version.py pyproject.toml
git commit -m "feat: add the desk package at 0.1.0"
```

If `desk` already exists, stay on it. Do not commit on `main`.

---

### Task 2: Ticker normalization

**Files:**
- Create: `desk/data/symbols.py`
- Create: `tests/test_desk_symbols.py`

**Interfaces:**
- Consumes: nothing
- Produces: `normalize_symbol(raw: str) -> str`, `safe_ticker_component(value: str, *, max_len: int = 32) -> str`, `resolve_ticker(raw: str) -> str`. `resolve_ticker` raises `ValueError` before any caller can hit the network.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from desk.data.symbols import normalize_symbol, resolve_ticker, safe_ticker_component


def test_broker_spellings_become_yahoo_symbols():
    assert normalize_symbol("XAUUSD+") == "GC=F"
    assert normalize_symbol("700.HK") == "0700.HK"
    assert normalize_symbol("0700.HK") == "0700.HK"
    assert normalize_symbol("600519.SH") == "600519.SS"
    assert normalize_symbol("EURUSD") == "EURUSD=X"
    assert normalize_symbol("BTCUSD") == "BTC-USD"


def test_unsafe_tickers_are_rejected():
    for bad in ("..", "/", ""):
        with pytest.raises(ValueError):
            safe_ticker_component(bad)


def test_resolve_rejects_traversal_before_normalizing():
    with pytest.raises(ValueError):
        resolve_ticker("../etc")
    assert resolve_ticker("XAUUSD+") == "GC=F"
```

Save as `tests/test_desk_symbols.py`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_desk_symbols.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'desk.data.symbols'`

- [ ] **Step 3: Copy the normalizer and add resolve_ticker**

```bash
cp tradingagents/dataflows/symbols.py desk/data/symbols.py
```

Append this function to `desk/data/symbols.py`. Do not change the copied functions.

```python
def resolve_ticker(raw: str) -> str:
    """Reject a path-unsafe ticker, then map what remains to Yahoo's symbol."""
    if not isinstance(raw, str):
        raise ValueError(f"ticker must be a non-empty string, got {raw!r}")
    safe_ticker_component(raw.strip())
    return normalize_symbol(raw)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_desk_symbols.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/data/symbols.py tests/test_desk_symbols.py
git commit -m "feat: resolve desk tickers to Yahoo symbols"
```

---

### Task 3: Snapshot command

**Files:**
- Create: `desk/data/errors.py`
- Create: `desk/data/prices.py`
- Create: `tests/test_snapshot.py`
- Modify: `desk/cli.py`

**Interfaces:**
- Consumes: `resolve_ticker(raw: str) -> str`
- Produces: `snapshot_text(ticker: str, *, frame: pd.DataFrame | None = None, now: datetime | None = None) -> str`. `fetch_daily(canonical: str) -> pd.DataFrame` with a `Date` column and `Open`, `High`, `Low`, `Close`, `Volume`. `DeskError(Exception)`. CLI `main(["snapshot", ticker])` prints the text and returns 0, or prints `DeskError` to stderr and returns 1.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from desk.cli import main
from desk.data.prices import snapshot_text


def _bars(dates, closes):
    return pd.DataFrame({
        "Date": pd.to_datetime(dates),
        "Open": closes,
        "High": [c + 1 for c in closes],
        "Low": [c - 1 for c in closes],
        "Close": closes,
        "Volume": [1000] * len(closes),
    })


def test_marker_uses_the_last_closed_row_and_matches_the_table(monkeypatch, capsys):
    frame = _bars(["2026-10-30", "2026-11-02"], [10.0, 187.25])
    text = snapshot_text("nvda", frame=frame, now=datetime(2026, 11, 3, tzinfo=ZoneInfo("America/New_York")))
    first = text.splitlines()[0]
    assert first == "SNAPSHOT NVDA 2026-11-02 187.25"
    assert "187.25" in text.split("SNAPSHOT", 1)[1]


def test_todays_partial_bar_is_not_the_anchor():
    frame = _bars(["2026-11-02", "2026-11-03"], [187.25, 999.0])
    text = snapshot_text(
        "NVDA",
        frame=frame,
        now=datetime(2026, 11, 3, 15, tzinfo=ZoneInfo("America/New_York")),
    )
    assert text.splitlines()[0] == "SNAPSHOT NVDA 2026-11-02 187.25"
    assert "999" not in text


def test_empty_series_exits_1_without_a_marker(monkeypatch, capsys):
    monkeypatch.setattr("desk.data.prices.fetch_daily", lambda canonical: _bars([], []))
    code = main(["snapshot", "NVDA"])
    captured = capsys.readouterr()
    assert code == 1
    assert "SNAPSHOT" not in captured.out
    assert captured.err


def test_alias_is_the_symbol_the_vendor_is_asked(monkeypatch):
    seen = {}

    def fetch(canonical):
        seen["canonical"] = canonical
        return _bars(["2026-10-30"], [1900.0])

    monkeypatch.setattr("desk.data.prices.fetch_daily", fetch)
    snapshot_text("XAUUSD+", now=datetime(2026, 11, 3, tzinfo=ZoneInfo("America/New_York")))
    assert seen["canonical"] == "GC=F"


def test_unsafe_ticker_does_not_call_the_vendor(monkeypatch):
    def fetch(canonical):
        raise AssertionError("vendor was called")

    monkeypatch.setattr("desk.data.prices.fetch_daily", fetch)
    code = main(["snapshot", ".."])
    assert code == 1
```

Save as `tests/test_snapshot.py`. `snapshot_text` calls `fetch_daily` in `desk.data.prices`, so the patch target is `desk.data.prices.fetch_daily`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_snapshot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'desk.data.prices'`

- [ ] **Step 3: Implement snapshot rendering and the command**

`desk/data/errors.py`:

```python
class DeskError(Exception):
    """A command cannot do its job. The CLI prints this and exits 1."""


class NoMarketDataError(DeskError):
    """The vendor returned no usable rows."""


class VendorUnavailableError(DeskError):
    """The vendor request failed. This says nothing about the instrument."""
```

`desk/data/prices.py`:

```python
"""Daily prices and the verified snapshot the market subagent must quote."""

from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from stockstats import wrap

from desk.data.errors import DeskError, NoMarketDataError, VendorUnavailableError
from desk.data.symbols import resolve_ticker

INDICATORS = (
    "close_10_ema", "close_50_sma", "close_200_sma",
    "rsi", "boll", "boll_ub", "boll_lb",
    "macd", "macds", "macdh", "atr",
)


def price_text(value: float) -> str:
    if not math.isfinite(value):
        return str(value)
    decimals = 2 if value == 0 else max(2, 5 - math.floor(math.log10(abs(value))))
    whole, _, fraction = f"{value:.{decimals}f}".partition(".")
    return f"{whole}.{fraction.rstrip('0').ljust(2, '0')}"


def session_timezone(canonical: str) -> str:
    if canonical.endswith(".HK"):
        return "Asia/Hong_Kong"
    if canonical.endswith(".T"):
        return "Asia/Tokyo"
    if canonical.endswith(".L"):
        return "Europe/London"
    if canonical.endswith("-USD") or canonical.endswith("=X"):
        return "UTC"
    return "America/New_York"


def fetch_daily(canonical: str) -> pd.DataFrame:
    try:
        data = yf.Ticker(canonical).history(period="2y", interval="1d", auto_adjust=False)
    except Exception as exc:
        raise VendorUnavailableError(f"Yahoo price request failed: {exc}") from exc
    if data is None or data.empty:
        raise NoMarketDataError(f"no prices for {canonical}")
    frame = data.reset_index()
    date_col = "Date" if "Date" in frame.columns else frame.columns[0]
    frame = frame.rename(columns={date_col: "Date"})
    keep = ["Date", "Open", "High", "Low", "Close", "Volume"]
    missing = [col for col in keep if col not in frame.columns]
    if missing:
        raise NoMarketDataError(f"price rows for {canonical} lack {missing}")
    return frame[keep]


def drop_open_session(frame: pd.DataFrame, today) -> pd.DataFrame:
    if frame.empty:
        return frame
    dates = pd.to_datetime(frame["Date"], utc=False).dt.date
    return frame.loc[dates < today].copy()


def snapshot_text(ticker: str, *, frame: pd.DataFrame | None = None, now: datetime | None = None) -> str:
    canonical = resolve_ticker(ticker)
    tz = ZoneInfo(session_timezone(canonical))
    moment = now or datetime.now(tz)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz)
    today = moment.astimezone(tz).date()
    if frame is None:
        frame = fetch_daily(canonical)
    closed = drop_open_session(frame, today)
    if closed.empty or closed["Close"].dropna().empty:
        raise NoMarketDataError(f"no closed session for {canonical}")
    closed = closed.dropna(subset=["Close"]).sort_values("Date")
    latest = closed.iloc[-1]
    anchor_date = pd.Timestamp(latest["Date"]).strftime("%Y-%m-%d")
    close = price_text(float(latest["Close"]))
    stock = wrap(closed.copy())
    indicator_lines = []
    for name in INDICATORS:
        try:
            value = stock.iloc[-1][name]
            rendered = "N/A" if pd.isna(value) else price_text(float(value))
        except Exception as exc:
            rendered = f"N/A ({type(exc).__name__})"
        indicator_lines.append(f"| {name} | {rendered} |")
    recent = closed.tail(30)
    recent_lines = [
        f"| {pd.Timestamp(row.Date).strftime('%Y-%m-%d')} | {price_text(float(row.Close))} |"
        for row in recent.itertuples(index=False)
    ]
    ohlcv = "\n".join(
        f"| {field} | {price_text(float(latest[field])) if field != 'Volume' else str(int(latest[field]))} |"
        for field in ("Open", "High", "Low", "Close", "Volume")
    )
    return "\n".join([
        f"SNAPSHOT {canonical} {anchor_date} {close}",
        "",
        "| Field | Value |",
        "|---|---:|",
        ohlcv,
        "",
        "| Indicator | Value |",
        "|---|---:|",
        *indicator_lines,
        "",
        "| Date | Close |",
        "|---|---:|",
        *recent_lines,
    ])
```

Replace `desk/cli.py` with:

```python
"""The desk command."""

import argparse
import sys

from desk.data.errors import DeskError
from desk.data.prices import snapshot_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="desk")
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("ticker")
    snap.set_defaults(func=_snapshot)
    args = parser.parse_args(argv)
    try:
        text = args.func(args)
    except DeskError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(text)
    return 0


def _snapshot(args) -> str:
    return snapshot_text(args.ticker)


if __name__ == "__main__":
    sys.exit(main())
```

In the empty-series test, patch `desk.data.prices.fetch_daily` to return an empty frame, and do not patch `desk.cli.fetch_daily`. `snapshot_text` calls `fetch_daily` in its own module, so the patch on `desk.data.prices.fetch_daily` is the one that counts when the CLI calls `snapshot_text`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_snapshot.py tests/test_desk_symbols.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/data/errors.py desk/data/prices.py desk/cli.py tests/test_snapshot.py
git commit -m "feat: print a verified price snapshot from desk snapshot"
```

---

### Task 4: Filings command

**Files:**
- Create: `desk/data/filings.py`
- Create: `tests/test_filings.py`
- Modify: `desk/cli.py`

**Interfaces:**
- Consumes: `resolve_ticker`, `DeskError`, `VendorUnavailableError`, `desk.__version__`
- Produces: `filings_text(ticker: str, *, sec=None, yahoo=None) -> str`. `fetch_sec(canonical: str)` and `fetch_yahoo(canonical: str)` return a `Statements` or raise `VendorUnavailableError`. `Statements` has `income`, `balance`, `cashflow` dataframes, and `period` of `"quarterly"` or `"annual"`. `redact_user_agent(text: str) -> str`.

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd
import pytest

from desk.cli import main
from desk.data.filings import Statements, filings_text, redact_user_agent


def _frame():
    return pd.DataFrame({"2026-09-30": [100.0]}, index=["Total Revenue"])


def _statements(period="quarterly"):
    frame = _frame()
    return Statements(income=frame, balance=frame, cashflow=frame, period=period)


def test_sec_quarterly_marker():
    text = filings_text("NVDA", sec=_statements(), yahoo=None)
    assert text.splitlines()[0] == "FILINGS NVDA quarterly sec"
    assert "Total Revenue" in text


def test_yahoo_fallback_when_sec_fails():
    text = filings_text("NVDA", sec=None, yahoo=_statements())
    assert text.splitlines()[0] == "FILINGS NVDA quarterly yahoo"


def test_annual_when_quarterly_is_empty():
    annual = _statements("annual")
    text = filings_text("NVDA", sec=annual, yahoo=None)
    assert text.splitlines()[0] == "FILINGS NVDA annual sec"


def test_both_sources_empty_exits_without_a_marker(monkeypatch, capsys):
    monkeypatch.setattr("desk.data.filings.fetch_sec", lambda canonical: None)
    monkeypatch.setattr("desk.data.filings.fetch_yahoo", lambda canonical: None)
    code = main(["filings", "NVDA"])
    captured = capsys.readouterr()
    assert code == 1
    assert "FILINGS" not in captured.out
    assert captured.err


def test_filings_text_rejects_when_both_sources_are_empty():
    with pytest.raises(Exception):
        filings_text("NVDA", sec=None, yahoo=None)


def test_sec_error_redacts_the_user_agent(monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "Ada Lovelace ada@example.com")
    blown = redact_user_agent("refused for Ada Lovelace ada@example.com")
    assert "ada@example.com" not in blown
    assert "Ada Lovelace" not in blown
```

Save as `tests/test_filings.py`. The CLI test patches `fetch_sec` and `fetch_yahoo` on `desk.data.filings`. `load_filings` must call those module globals.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_filings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'desk.data.filings'`

- [ ] **Step 3: Implement filings**

`desk/data/filings.py`:

```python
"""Latest income statement, balance sheet, and cash flow."""

from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd
import requests
import yfinance as yf

from desk import __version__
from desk.data.errors import DeskError, VendorUnavailableError
from desk.data.symbols import resolve_ticker


@dataclass
class Statements:
    income: pd.DataFrame | None
    balance: pd.DataFrame | None
    cashflow: pd.DataFrame | None
    period: str  # "quarterly" or "annual"


def user_agent() -> str:
    configured = os.getenv("SEC_EDGAR_USER_AGENT", "").strip()
    return configured or f"desk/{__version__} (contact@example.com)"


def redact_user_agent(text: str) -> str:
    agent = user_agent()
    return text.replace(agent, "***") if agent else text


def _usable(frame: pd.DataFrame | None) -> bool:
    return frame is not None and not frame.empty


def _prefer(quarterly: Statements | None, annual: Statements | None) -> Statements | None:
    if quarterly is not None and all(_usable(getattr(quarterly, name)) for name in ("income", "balance", "cashflow")):
        return quarterly
    if annual is not None and all(_usable(getattr(annual, name)) for name in ("income", "balance", "cashflow")):
        return annual
    return None


def _render_frame(title: str, frame: pd.DataFrame) -> str:
    return f"## {title}\n\n" + frame.to_string()


def filings_text(ticker: str, *, sec: Statements | None = None, yahoo: Statements | None = None) -> str:
    canonical = resolve_ticker(ticker)
    chosen = _prefer(sec, None)
    source = "sec"
    if chosen is None:
        chosen = _prefer(yahoo, None)
        source = "yahoo"
    if chosen is None:
        raise DeskError(f"no statements for {canonical}")
    body = "\n\n".join([
        _render_frame("Income statement", chosen.income),
        _render_frame("Balance sheet", chosen.balance),
        _render_frame("Cash flow", chosen.cashflow),
    ])
    return f"FILINGS {canonical} {chosen.period} {source}\n\n{body}"


def _yf_statements(canonical: str, period: str) -> Statements:
    ticker = yf.Ticker(canonical)
    if period == "quarterly":
        income, balance, cash = ticker.quarterly_income_stmt, ticker.quarterly_balance_sheet, ticker.quarterly_cashflow
    else:
        income, balance, cash = ticker.income_stmt, ticker.balance_sheet, ticker.cashflow
    return Statements(income=income, balance=balance, cashflow=cash, period=period)


def fetch_yahoo(canonical: str) -> Statements | None:
    try:
        quarterly = _yf_statements(canonical, "quarterly")
        if _prefer(quarterly, None):
            return quarterly
        annual = _yf_statements(canonical, "annual")
        return annual if _prefer(annual, None) else None
    except Exception as exc:
        raise VendorUnavailableError(redact_user_agent(f"Yahoo statements failed: {exc}")) from exc


def fetch_sec(canonical: str) -> Statements | None:
    """Latest quarter from SEC company facts. None when this ticker is not a filer.

    A failed request raises VendorUnavailableError with the user agent redacted.
    Returning a Statements object is enough for the command. Vintage reconstruction
    is not performed: the most recent reported quarter available today is the value.
    """
    try:
        mapping = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": user_agent()},
            timeout=30,
        )
        mapping.raise_for_status()
        cik = None
        for row in mapping.json().values():
            if str(row.get("ticker", "")).upper() == canonical:
                cik = str(row["cik_str"]).zfill(10)
                break
        if cik is None:
            return None
        facts = requests.get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            headers={"User-Agent": user_agent()},
            timeout=30,
        )
        facts.raise_for_status()
    except requests.RequestException as exc:
        body = ""
        response = getattr(exc, "response", None)
        if response is not None and response.text:
            body = response.text[:500]
        raise VendorUnavailableError(redact_user_agent(f"SEC request failed: {exc} {body}")) from exc
    us_gaap = facts.json().get("facts", {}).get("us-gaap", {})
    income = _latest_fact(us_gaap, ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"))
    balance = _latest_fact(us_gaap, ("Assets",))
    cash = _latest_fact(us_gaap, ("NetCashProvidedByUsedInOperatingActivities",))
    if income is None and balance is None and cash is None:
        return None
    return Statements(income=income, balance=balance, cashflow=cash, period="quarterly")


def _latest_fact(us_gaap: dict, tags: tuple[str, ...]) -> pd.DataFrame | None:
    for tag in tags:
        units = us_gaap.get(tag, {}).get("units", {})
        rows = units.get("USD") or next(iter(units.values()), [])
        quarters = [row for row in rows if row.get("fp") in {"Q1", "Q2", "Q3", "Q4"} and "end" in row and "val" in row]
        if not quarters:
            continue
        latest = max(quarters, key=lambda row: row["end"])
        return pd.DataFrame({latest["end"]: [latest["val"]]}, index=[tag])
    return None


def load_filings(ticker: str) -> str:
    canonical = resolve_ticker(ticker)
    sec = None
    try:
        sec = fetch_sec(canonical)
    except VendorUnavailableError:
        sec = None
    yahoo = None
    if _prefer(sec, None) is None:
        try:
            yahoo = fetch_yahoo(canonical)
        except VendorUnavailableError as exc:
            if sec is None:
                raise DeskError(str(exc)) from exc
    return filings_text(ticker, sec=sec, yahoo=yahoo)
```

`filings_text` as written prefers a SEC `Statements` even when its frames are empty if the object is non-None. `_prefer(sec, None)` returns None when frames are empty, so an empty SEC object must be passed as a Statements with empty frames, not None. `load_filings` should pass SEC through only when `_prefer` accepts it. Change the last line's call to:

```python
def load_filings(ticker: str) -> str:
    canonical = resolve_ticker(ticker)
    sec = None
    try:
        sec = fetch_sec(canonical)
    except VendorUnavailableError as exc:
        sec_error = exc
    else:
        sec_error = None
    yahoo = None
    if _prefer(sec, None) is None:
        try:
            yahoo = fetch_yahoo(canonical)
        except VendorUnavailableError as exc:
            raise DeskError(redact_user_agent(str(sec_error or exc))) from exc
    if _prefer(sec, None) is None and _prefer(yahoo, None) is None:
        raise DeskError(f"no statements for {canonical}")
    return filings_text(
        ticker,
        sec=sec if _prefer(sec, None) else None,
        yahoo=yahoo if _prefer(yahoo, None) else None,
    )
```

Add the filings subcommand in `desk/cli.py`:

```python
from desk.data.filings import load_filings


def _filings(args) -> str:
    return load_filings(args.ticker)
```

Register it next to snapshot:

```python
fil = sub.add_parser("filings")
fil.add_argument("ticker")
fil.set_defaults(func=_filings)
```

`filings_text` must accept a SEC annual `Statements` and emit `annual sec`. `_prefer` looks at `period` only by the caller passing the annual object as `sec`. The test `test_annual_when_quarterly_is_empty` passes `sec=annual`. `filings_text` uses `chosen.period`, so the marker is `FILINGS NVDA annual sec`. Good.

When both arguments are None, `filings_text` raises `DeskError`. The CLI test patches the fetchers and calls `main`, which calls `load_filings`, not `filings_text` directly. `load_filings` with both fetchers returning None raises `DeskError`. The CLI catches it.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_filings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/data/filings.py desk/cli.py tests/test_filings.py
git commit -m "feat: print latest statements from desk filings"
```

---

### Task 5: Record command

**Files:**
- Create: `desk/data/ledger.py`
- Create: `tests/test_record.py`
- Modify: `desk/cli.py`

**Interfaces:**
- Consumes: `snapshot_text(ticker) -> str`, `DeskError`
- Produces: `LEDGER = Path.home() / ".tradingagents" / "ledger.jsonl"`. `append_record(ticker: str, rating: str, snapshot: str, *, now: datetime | None = None, ledger: Path | None = None) -> dict`. The dict has every field in the spec, with return fields `null`. `parse_rating(text: str) -> str`.

- [ ] **Step 1: Write the failing test**

```python
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from desk.cli import main
from desk.data.prices import snapshot_text


def _frame():
    return pd.DataFrame({
        "Date": pd.to_datetime(["2026-11-02"]),
        "Open": [187.0], "High": [188.0], "Low": [186.0], "Close": [187.25],
        "Volume": [1000],
    })


def _patch_snapshot(monkeypatch):
    text = snapshot_text(
        "NVDA",
        frame=_frame(),
        now=datetime(2026, 11, 3, tzinfo=ZoneInfo("America/New_York")),
    )
    monkeypatch.setattr("desk.data.ledger.snapshot_text", lambda ticker: text)


def test_hold_stores_the_snapshot_close(monkeypatch, tmp_path, capsys):
    _patch_snapshot(monkeypatch)
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    code = main(["record", "NVDA", "Hold"])
    row = json.loads(ledger.read_text(encoding="utf-8"))
    assert code == 0
    assert row["rating"] == "Hold"
    assert row["anchor_close"] == 187.25
    assert row["anchor_date"] == "2026-11-02"
    assert row["benchmark"] == "SPY"
    assert row["ret_5"] is None and row["ret_21"] is None
    assert "187.25" in capsys.readouterr().out


def test_lowercase_rating_is_canonical(monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch)
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    assert main(["record", "NVDA", "buy"]) == 0
    assert json.loads(ledger.read_text(encoding="utf-8"))["rating"] == "Buy"


@pytest_bad = ("REVIEW", "", "Maybe")


def test_bad_ratings_write_nothing(monkeypatch, tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)

    def explode(ticker):
        raise AssertionError("snapshot ran")

    monkeypatch.setattr("desk.data.ledger.snapshot_text", explode)
    for rating in ("REVIEW", "Maybe"):
        assert main(["record", "NVDA", rating]) == 1
    assert not ledger.exists()


def test_snapshot_failure_writes_nothing(monkeypatch, tmp_path):
    from desk.data.errors import NoMarketDataError
    monkeypatch.setattr("desk.data.ledger.LEDGER", tmp_path / "ledger.jsonl")

    def fail(ticker):
        raise NoMarketDataError("no prices")

    monkeypatch.setattr("desk.data.ledger.snapshot_text", fail)
    assert main(["record", "NVDA", "Hold"]) == 1
    assert not (tmp_path / "ledger.jsonl").exists()


def test_two_records_are_two_lines(monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch)
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    assert main(["record", "NVDA", "Buy"]) == 0
    assert main(["record", "NVDA", "Sell"]) == 0
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
```

Save as `tests/test_record.py`. Remove the unused `pytest_bad` name before committing. Import nothing you do not use.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_record.py -v`
Expected: FAIL with `ModuleNotFoundError` or `SystemExit` because `record` is not a subcommand

- [ ] **Step 3: Implement the ledger append**

`desk/data/ledger.py`:

```python
"""Decision ledger. Scores are filled later and never sent back to a desk."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from desk.data.errors import DeskError
from desk.data.prices import snapshot_text

LEDGER = Path.home() / ".tradingagents" / "ledger.jsonl"
RATINGS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")


def parse_rating(text: str) -> str:
    match = {name.lower(): name for name in RATINGS}
    found = match.get(text.strip().lower())
    if found is None:
        raise DeskError(f"rating must be one of {', '.join(RATINGS)}")
    return found


def parse_snapshot_marker(text: str) -> tuple[str, str, float]:
    try:
        kind, ticker, anchor_date, close = text.splitlines()[0].split()
    except (IndexError, ValueError) as exc:
        raise DeskError("snapshot did not start with a SNAPSHOT line") from exc
    if kind != "SNAPSHOT":
        raise DeskError("snapshot did not start with a SNAPSHOT line")
    return ticker, anchor_date, float(close)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def append_record(ticker: str, rating: str, *, ledger: Path | None = None) -> dict:
    canonical_rating = parse_rating(rating)
    path = ledger or LEDGER
    text = snapshot_text(ticker)
    symbol, anchor_date, close = parse_snapshot_marker(text)
    row = {
        "id": str(uuid.uuid4()),
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "ticker": symbol,
        "rating": canonical_rating,
        "anchor_date": anchor_date,
        "anchor_close": close,
        "benchmark": "SPY",
        "ret_5": None,
        "alpha_5": None,
        "exit_date_5": None,
        "ret_21": None,
        "alpha_21": None,
        "exit_date_21": None,
    }
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    _write(path, existing + json.dumps(row) + "\n")
    return row
```

`parse_rating` runs before `snapshot_text`, so a bad rating does not fetch. The test asserts the snapshot function is not called for `REVIEW` and `Maybe`.

Add to `desk/cli.py`:

```python
import json

from desk.data.ledger import append_record


def _record(args) -> str:
    return json.dumps(append_record(args.ticker, args.rating), indent=2)
```

```python
rec = sub.add_parser("record")
rec.add_argument("ticker")
rec.add_argument("rating")
rec.set_defaults(func=_record)
```

Tests patch `desk.data.ledger.snapshot_text` and `desk.data.ledger.LEDGER`. `append_record` uses those module globals. `main` calls `append_record` with no ledger argument, so the patch of `LEDGER` applies.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_record.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desk/data/ledger.py desk/cli.py tests/test_record.py
git commit -m "feat: append a decision row from desk record"
```

---

### Task 6: Score command

**Files:**
- Modify: `desk/data/ledger.py`
- Modify: `desk/cli.py`
- Create: `tests/test_score.py`

**Interfaces:**
- Consumes: `LEDGER`, `append_record`, the row shape from Task 5
- Produces: `score_ledger(*, ledger: Path | None = None) -> ScoreResult` with fields `stdout: str`, `code: int`, `stderr: str`. `closes_for(canonical: str) -> pd.Series` indexed by `datetime.date`. Tests patch `desk.data.ledger.closes_for`. The default calls `fetch_daily`.

- [ ] **Step 1: Write the failing test**

```python
import json
from datetime import date, timedelta

import pandas as pd

from desk.cli import main
from desk.data.errors import VendorUnavailableError


def _row(anchor=date(2026, 1, 2), close=100.0):
    return {
        "id": "row-1",
        "decided_at": "2026-01-02T00:00:00+00:00",
        "ticker": "NVDA",
        "rating": "Buy",
        "anchor_date": anchor.isoformat(),
        "anchor_close": close,
        "benchmark": "SPY",
        "ret_5": None, "alpha_5": None, "exit_date_5": None,
        "ret_21": None, "alpha_21": None, "exit_date_21": None,
    }


def _series(anchor: date, n: int, start: float, step: float):
    days = [anchor + timedelta(days=i + 1) for i in range(n)]
    return pd.Series([start + step * i for i in range(n)], index=days)


def _write(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_five_sessions_fill_only_the_short_horizon(monkeypatch, tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    _write(ledger, [_row(anchor)])
    stock = _series(anchor, 5, 110, 0)
    spy_index = [anchor, *list(_series(anchor, 5, 400, 0).index)]
    spy = pd.Series([400.0] * len(spy_index), index=spy_index)

    def closes_for(canonical):
        return stock if canonical == "NVDA" else spy

    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    monkeypatch.setattr("desk.data.ledger.closes_for", closes_for)
    assert main(["score"]) == 0
    saved = json.loads(ledger.read_text(encoding="utf-8"))
    assert saved["ret_5"] == (110 / 100) - 1
    assert saved["exit_date_5"] == (anchor + timedelta(days=5)).isoformat()
    assert saved["alpha_5"] == saved["ret_5"] - ((400 / 400) - 1)
    assert saved["ret_21"] is None
    out = capsys.readouterr().out.lower()
    assert "reflection" not in out
    assert "buy" not in out


def test_second_run_does_not_change_a_filled_horizon(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    row = _row(anchor)
    row["ret_5"] = 0.5
    row["alpha_5"] = 0.25
    row["exit_date_5"] = "2026-01-09"
    _write(ledger, [row])
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    monkeypatch.setattr(
        "desk.data.ledger.closes_for",
        lambda canonical: _series(anchor, 21, 1, 1),
    )
    assert main(["score"]) == 0
    saved = json.loads(ledger.read_text(encoding="utf-8"))
    assert saved["ret_5"] == 0.5
    assert saved["ret_21"] is not None


def test_short_series_stays_empty_and_exits_0(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    _write(ledger, [_row(anchor)])
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)
    monkeypatch.setattr("desk.data.ledger.closes_for", lambda canonical: _series(anchor, 3, 10, 0))
    assert main(["score"]) == 0
    saved = json.loads(ledger.read_text(encoding="utf-8"))
    assert saved["ret_5"] is None


def test_a_failed_fetch_of_a_sibling_does_not_drop_a_good_row(monkeypatch, tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    good = _row(anchor)
    bad = _row(anchor)
    bad["id"] = "row-2"
    bad["ticker"] = "AAPL"
    _write(ledger, [good, bad])
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)

    def closes_for(canonical):
        if canonical == "AAPL":
            raise VendorUnavailableError("down")
        return _series(anchor, 5, 110, 0)

    monkeypatch.setattr("desk.data.ledger.closes_for", closes_for)
    assert main(["score"]) == 1
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    by_id = {row["id"]: row for row in rows}
    assert by_id["row-1"]["ret_5"] == 0.1
    assert by_id["row-2"]["ret_5"] is None
    assert "AAPL" in capsys.readouterr().err


def test_missing_spy_cover_still_writes_the_raw_return(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    anchor = date(2026, 1, 2)
    _write(ledger, [_row(anchor)])
    monkeypatch.setattr("desk.data.ledger.LEDGER", ledger)

    def closes_for(canonical):
        if canonical == "SPY":
            return pd.Series(dtype=float)
        return _series(anchor, 5, 110, 0)

    monkeypatch.setattr("desk.data.ledger.closes_for", closes_for)
    assert main(["score"]) == 0
    saved = json.loads(ledger.read_text(encoding="utf-8"))
    assert saved["ret_5"] == 0.1
    assert saved["alpha_5"] is None
```

Save as `tests/test_score.py`.

The 5-session series built with `timedelta(days=1)` is five calendar days, which this test treats as five sessions because the fixture index is the session list. Production `closes_for` must drop the anchor date itself and count only later rows. The fixture starts at `anchor + 1 day`, so the 5th row is `anchor + 5 days`. `exit_date_5` expected value must match that. Alpha versus a flat SPY at 400 is `ret_5 - 0`.

`test_second_run` uses a 21-point series. The already stored `ret_5` stays `0.5`. `ret_21` becomes a number. The 21st session date is `anchor + 21 days` only if the series index is `anchor + 1 ... anchor + 21`. `_series(anchor, 21, ...)` indexes `anchor+1` through `anchor+21`. Good.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_score.py -v`
Expected: FAIL because `score` is not a subcommand

- [ ] **Step 3: Implement scoring**

Add to `desk/data/ledger.py`:

```python
from datetime import date
from typing import NamedTuple

import pandas as pd

from desk.data.prices import fetch_daily

HORIZONS = (5, 21)


def closes_for(canonical: str) -> pd.Series:
    frame = fetch_daily(canonical)
    dates = pd.to_datetime(frame["Date"]).dt.date
    series = pd.Series(frame["Close"].astype(float).to_numpy(), index=list(dates))
    series = series[series > 0]
    return series.sort_index()


def _nth_later(series: pd.Series, anchor: date, n: int):
    later = [(day, float(price)) for day, price in series.items() if day > anchor]
    if len(later) < n:
        return None
    return later[n - 1]


def _spy_return(spy: pd.Series, anchor: date, exit_day: date) -> float | None:
    before = [(day, price) for day, price in spy.items() if day <= anchor]
    after = [(day, price) for day, price in spy.items() if day <= exit_day]
    if not before or not after:
        return None
    start, end = before[-1][1], after[-1][1]
    if start <= 0:
        return None
    return (end / start) - 1


class ScoreResult(NamedTuple):
    stdout: str
    code: int
    stderr: str


def _filled(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def score_ledger(*, ledger: Path | None = None) -> ScoreResult:
    path = ledger or LEDGER
    if not path.exists():
        return ScoreResult("", 0, "")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    stdout_lines = []
    stderr_lines = []
    for row in rows:
        touched = False
        anchor = date.fromisoformat(row["anchor_date"])
        try:
            stock = closes_for(row["ticker"])
            spy = closes_for(row["benchmark"])
        except DeskError as exc:
            stderr_lines.append(f"{row['ticker']} {row['id']}: {exc}")
            continue
        for n in HORIZONS:
            key = f"ret_{n}"
            if _filled(row.get(key)):
                continue
            found = _nth_later(stock, anchor, n)
            if found is None:
                continue
            exit_day, exit_close = found
            raw = (exit_close / float(row["anchor_close"])) - 1
            row[key] = raw
            row[f"exit_date_{n}"] = exit_day.isoformat()
            bench = _spy_return(spy, anchor, exit_day)
            row[f"alpha_{n}"] = None if bench is None else raw - bench
            touched = True
            stdout_lines.append(f"scored {row['id']} ret_{n}")
        if not touched and not any(_filled(row.get(f"ret_{n}")) for n in HORIZONS):
            stdout_lines.append(f"skipped {row['id']}")
    _write(path, "".join(json.dumps(row) + "\n" for row in rows))
    return ScoreResult("\n".join(stdout_lines), 1 if stderr_lines else 0, "\n".join(stderr_lines))
```

`closes_for` stays a module-level function. `score_ledger` calls that name, so tests patch `desk.data.ledger.closes_for`. An empty SPY series is not an error: `alpha_N` stays null and `ret_N` is still written. A raised `DeskError` from either fetch leaves the new fields null, names the ticker on stderr, and makes the exit code 1 after the other rows are written.

In `desk/cli.py`, `main` becomes:

```python
from desk.data.ledger import ScoreResult, append_record, score_ledger


def _score(args) -> ScoreResult:
    return score_ledger()
```

```python
scr = sub.add_parser("score")
scr.set_defaults(func=_score)
```

```python
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except DeskError as exc:
        print(exc, file=sys.stderr)
        return 1
    if isinstance(result, ScoreResult):
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.code
    print(result)
    return 0
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_score.py tests/test_record.py tests/test_snapshot.py tests/test_filings.py tests/test_desk_symbols.py tests/test_desk_version.py -v`
Expected: PASS

Also run the old suite so this plan did not break it:

Run: `pytest -q`
Expected: the new tests pass and the previous suite still passes

- [ ] **Step 5: Commit**

```bash
git add desk/data/ledger.py desk/cli.py tests/test_score.py
git commit -m "feat: fill 5-day and 21-day returns from desk score"
```
