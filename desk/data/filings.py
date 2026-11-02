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
