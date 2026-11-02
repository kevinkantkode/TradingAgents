"""Daily prices and the verified snapshot the market subagent must quote."""

from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from stockstats import StockDataFrame

from tradingagents.data.errors import TradingAgentsError, NoMarketDataError, VendorUnavailableError
from tradingagents.data.symbols import resolve_ticker

INDICATORS = (
    "close_10_ema", "close_50_sma", "close_200_sma",
    "rsi", "boll", "boll_ub", "boll_lb",
    "macd", "macds", "macdh", "atr",
)

INDICATOR_MIN_BARS = {
    "close_10_ema": 10,
    "close_50_sma": 50,
    "close_200_sma": 200,
    "rsi": 14,
    "boll": 20,
    "boll_ub": 20,
    "boll_lb": 20,
    "macd": 26,
    "macds": 26,
    "macdh": 26,
    "atr": 14,
}


def price_text(value: float) -> str:
    if not math.isfinite(value):
        return str(value)
    decimals = 2 if value == 0 else max(2, 5 - math.floor(math.log10(abs(value))))
    whole, _, fraction = f"{value:.{decimals}f}".partition(".")
    return f"{whole}.{fraction.rstrip('0').ljust(2, '0')}"


def session_timezone(canonical: str) -> str:
    if canonical.endswith(".HK"):
        return "Asia/Hong_Kong"
    if canonical.endswith(".SS") or canonical.endswith(".SZ"):
        return "Asia/Shanghai"
    if canonical.endswith(".T"):
        return "Asia/Tokyo"
    if canonical.endswith(".L"):
        return "Europe/London"
    index_tz = {
        "^HSI": "Asia/Hong_Kong",
        "^N225": "Asia/Tokyo",
        "^FTSE": "Europe/London",
        "^GDAXI": "Europe/Berlin",
        "^FCHI": "Europe/Paris",
        "^STOXX50E": "Europe/Berlin",
    }
    if canonical in index_tz:
        return index_tz[canonical]
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
    try:
        canonical = resolve_ticker(ticker)
    except ValueError as exc:
        raise TradingAgentsError(str(exc)) from exc
    tz = ZoneInfo(session_timezone(canonical))
    moment = now or datetime.now(tz)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz)
    today = moment.astimezone(tz).date()
    if frame is None:
        frame = fetch_daily(canonical)
    closed = drop_open_session(frame, today)
    if closed.empty:
        raise NoMarketDataError(f"no closed session for {canonical}")
    closed = closed.sort_values("Date")
    latest = closed.iloc[-1]
    for field in ("Open", "High", "Low", "Close", "Volume"):
        value = latest[field]
        if pd.isna(value):
            raise NoMarketDataError(f"anchor row for {canonical} has non-finite {field}")
        if not math.isfinite(float(value)):
            raise NoMarketDataError(f"anchor row for {canonical} has non-finite {field}")
    closed = closed.dropna(subset=["Close"])
    if closed.empty:
        raise NoMarketDataError(f"no closed session for {canonical}")
    anchor_date = pd.Timestamp(latest["Date"]).strftime("%Y-%m-%d")
    close = price_text(float(latest["Close"]))
    stats_input = closed.rename(columns={
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })
    stock = StockDataFrame.retype(stats_input)
    indicator_lines = []
    for name in INDICATORS:
        need = INDICATOR_MIN_BARS[name]
        if len(closed) < need:
            rendered = "N/A"
        else:
            try:
                value = stock[name].iloc[-1]
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
