"""Latest income statement, balance sheet, and cash flow."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

import pandas as pd
import requests
import yfinance as yf

from tradingagents import __version__
from tradingagents.data.errors import TradingAgentsError, VendorUnavailableError
from tradingagents.data.symbols import resolve_ticker


@dataclass
class Statements:
    income: pd.DataFrame | None
    balance: pd.DataFrame | None
    cashflow: pd.DataFrame | None
    period: str  # "quarterly" or "annual"


@dataclass
class YahooFilings:
    """Full Yahoo statements. SEC one-cell facts must not replace these."""

    quarterly: Statements | None
    annual: Statements | None
    insider: pd.DataFrame | None


# ponytail: four statement columns and fifteen insider rows. Raise the caps
# if a run needs a longer history in the prompt.
_STATEMENT_COLUMNS = 4
_INSIDER_ROWS = 15


def user_agent() -> str:
    configured = os.getenv("SEC_EDGAR_USER_AGENT", "").strip()
    return configured or f"tradingagents/{__version__} (contact@example.com)"


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


def _column_keys(frame: pd.DataFrame | None) -> set[tuple]:
    if frame is None or frame.empty:
        return set()
    keys = set()
    for column in frame.columns:
        try:
            keys.add(("ts", pd.Timestamp(column).normalize()))
        except (TypeError, ValueError, OverflowError):
            keys.add(("raw", str(column)))
    return keys


def _recent_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or len(frame.columns) <= _STATEMENT_COLUMNS:
        return frame
    try:
        order = sorted(frame.columns, key=lambda column: pd.Timestamp(column), reverse=True)
    except (TypeError, ValueError, OverflowError):
        return frame
    return frame.loc[:, order[:_STATEMENT_COLUMNS]]


def _adds_a_year(quarterly: Statements, annual: Statements | None) -> bool:
    if annual is None:
        return False
    covered: set[tuple] = set()
    extra: set[tuple] = set()
    for name in ("income", "balance", "cashflow"):
        covered |= _column_keys(getattr(quarterly, name))
        extra |= _column_keys(getattr(annual, name))
    return bool(extra - covered)


def _recent_insider(frame: pd.DataFrame) -> pd.DataFrame:
    dated = [column for column in frame.columns if "date" in str(column).lower()]
    ordered = frame
    if dated:
        try:
            ordered = frame.sort_values(dated[0], ascending=False)
        except (TypeError, ValueError):
            ordered = frame
    return ordered.head(_INSIDER_ROWS)


def _render_frame(title: str, frame: pd.DataFrame) -> str:
    return f"## {title}\n\n" + _recent_columns(frame).to_string()


def _canonical(ticker: str) -> str:
    try:
        return resolve_ticker(ticker)
    except ValueError as exc:
        raise TradingAgentsError(str(exc)) from exc


def _sec_cross_check(sec: Statements | None) -> str | None:
    if sec is None:
        return None
    labels = (
        ("income", "Revenue"),
        ("balance", "Assets"),
        ("cashflow", "Operating cash flow"),
    )
    parts = ["## SEC company facts", ""]
    found = False
    for name, label in labels:
        frame = getattr(sec, name)
        if not _usable(frame):
            continue
        found = True
        parts.append(f"### {label}")
        parts.append("")
        parts.append(frame.to_string())
        parts.append("")
    if not found:
        return None
    return "\n".join(parts).rstrip()


def _statement_blocks(prefix: str, chosen: Statements) -> list[str]:
    return [
        _render_frame(f"{prefix}Income statement", chosen.income),
        _render_frame(f"{prefix}Balance sheet", chosen.balance),
        _render_frame(f"{prefix}Cash flow", chosen.cashflow),
    ]


def filings_text(
    ticker: str,
    *,
    sec: Statements | None = None,
    yahoo: Statements | None = None,
    annual: Statements | None = None,
    insider: pd.DataFrame | None = None,
    sec_note: str | None = None,
) -> str:
    canonical = _canonical(ticker)
    yahoo_quarter = None
    yahoo_annual = annual if _prefer(annual, None) else None
    if _prefer(yahoo, None):
        if yahoo.period == "annual":
            yahoo_annual = yahoo
        else:
            yahoo_quarter = yahoo
    sec_chosen = _prefer(sec, None)
    extra_annual = None
    if yahoo_quarter is not None:
        chosen = yahoo_quarter
        source = "yahoo"
        if _adds_a_year(yahoo_quarter, yahoo_annual):
            extra_annual = yahoo_annual
    elif yahoo_annual is not None:
        chosen = yahoo_annual
        source = "yahoo"
    elif sec_chosen is not None:
        chosen = sec_chosen
        source = "sec"
    else:
        raise TradingAgentsError(f"no statements for {canonical}")
    blocks = _statement_blocks("", chosen)
    if extra_annual is not None:
        blocks.extend(_statement_blocks("Annual ", extra_annual))
    if insider is not None and not insider.empty:
        blocks.append("## Insider transactions\n\n" + _recent_insider(insider).to_string())
    if source == "yahoo":
        cross_check = _sec_cross_check(sec)
        if cross_check:
            blocks.append(cross_check)
        elif sec_note:
            blocks.append("## SEC company facts\n\n" + sec_note)
    body = "\n\n".join(blocks)
    return f"FILINGS {canonical} {chosen.period} {source}\n\n{body}"


def _yf_statements(ticker: yf.Ticker, period: str) -> Statements:
    if period == "quarterly":
        income = ticker.quarterly_income_stmt
        balance = ticker.quarterly_balance_sheet
        cash = ticker.quarterly_cashflow
    else:
        income = ticker.income_stmt
        balance = ticker.balance_sheet
        cash = ticker.cashflow
    return Statements(income=income, balance=balance, cashflow=cash, period=period)


def _insider_frame(ticker: yf.Ticker) -> pd.DataFrame | None:
    try:
        frame = ticker.insider_transactions
    except Exception:
        return None
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    return frame


def fetch_yahoo(canonical: str) -> YahooFilings | None:
    try:
        ticker = yf.Ticker(canonical)
        quarterly = _prefer(_yf_statements(ticker, "quarterly"), None)
        annual = _prefer(_yf_statements(ticker, "annual"), None)
        insider = _insider_frame(ticker)
    except Exception as exc:
        raise VendorUnavailableError(redact_user_agent(f"Yahoo statements failed: {exc}")) from exc
    if quarterly is None and annual is None:
        return None
    return YahooFilings(quarterly=quarterly, annual=annual, insider=insider)


def fetch_sec(canonical: str) -> Statements | None:
    """Latest quarter from SEC company facts. None when this ticker is not a filer.

    A failed request raises VendorUnavailableError with the user agent redacted.
    Returning a Statements object is enough for the command. Vintage reconstruction
    is not performed: the most recent reported quarter available today is the value.
    """
    facts = None
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
        us_gaap = facts.json().get("facts", {}).get("us-gaap", {})
        income = _latest_fact(us_gaap, ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"))
        balance = _latest_fact(us_gaap, ("Assets",))
        cash = _latest_fact(us_gaap, ("NetCashProvidedByUsedInOperatingActivities",))
        if income is None and balance is None and cash is None:
            return None
        return Statements(income=income, balance=balance, cashflow=cash, period="quarterly")
    except (requests.RequestException, KeyError, TypeError, AttributeError) as exc:
        body = ""
        response = getattr(exc, "response", None)
        if response is not None and response.text:
            body = redact_user_agent(response.text[:500])
        elif facts is not None and facts.text:
            body = redact_user_agent(facts.text[:500])
        raise VendorUnavailableError(redact_user_agent(f"SEC request failed: {exc} {body}")) from exc


def _fact_span_days(row: dict) -> int | None:
    """Days from start to end. None when start is missing or not a date."""
    start = row.get("start")
    if not start:
        return None
    try:
        return (date.fromisoformat(row["end"]) - date.fromisoformat(start)).days
    except (TypeError, ValueError, KeyError):
        return None


def _latest_fact(us_gaap: dict, tags: tuple[str, ...]) -> pd.DataFrame | None:
    for tag in tags:
        units = us_gaap.get(tag, {}).get("units", {})
        rows = units.get("USD") or next(iter(units.values()), [])
        quarters = [row for row in rows if row.get("fp") in {"Q1", "Q2", "Q3", "Q4"} and "end" in row and "val" in row]
        if not quarters:
            continue
        latest_end = max(row["end"] for row in quarters)
        at_end = [row for row in quarters if row["end"] == latest_end]
        spans = [_fact_span_days(row) for row in at_end]
        known = [span for span in spans if span is not None]
        # A missing start is an instant (Assets) only when every sibling is one.
        # If any row has a real span, a missing start must not beat that quarter.
        unknown = max(known) + 1 if known else 0
        ranks = [unknown if span is None else span for span in spans]
        min_span = min(ranks)
        shortest = [row for row, rank in zip(at_end, ranks, strict=True) if rank == min_span]
        latest = max(shortest, key=lambda row: row.get("filed", ""))
        return pd.DataFrame({latest["end"]: [latest["val"]]}, index=[tag])
    return None


def load_filings(ticker: str) -> str:
    canonical = _canonical(ticker)
    yahoo_error = None
    try:
        pack = fetch_yahoo(canonical)
    except VendorUnavailableError as exc:
        pack = None
        yahoo_error = exc
    sec = None
    sec_error = None
    try:
        sec = fetch_sec(canonical)
    except VendorUnavailableError as exc:
        sec_error = exc
    if pack is not None:
        return filings_text(
            ticker,
            sec=sec,
            yahoo=pack.quarterly,
            annual=pack.annual,
            insider=pack.insider,
            sec_note=None if sec_error is None else redact_user_agent(str(sec_error)),
        )
    if sec_error is not None:
        raise TradingAgentsError(redact_user_agent(str(sec_error))) from sec_error
    if _prefer(sec, None) is None:
        if yahoo_error is not None:
            raise TradingAgentsError(redact_user_agent(str(yahoo_error))) from yahoo_error
        raise TradingAgentsError(f"no statements for {canonical}")
    return filings_text(ticker, sec=sec)
