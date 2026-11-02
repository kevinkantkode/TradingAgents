import pandas as pd
import pytest
import requests

from desk.cli import main
from desk.data.errors import DeskError, VendorUnavailableError
from desk.data.filings import Statements, YahooFilings, _latest_fact, filings_text, load_filings


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
    with pytest.raises(DeskError):
        filings_text("NVDA", sec=None, yahoo=None)


def test_sec_outage_with_empty_yahoo_reports_the_sec_error(monkeypatch, capsys):
    def sec_timeout(canonical):
        raise VendorUnavailableError("SEC request failed: timeout")

    monkeypatch.setattr("desk.data.filings.fetch_sec", sec_timeout)
    monkeypatch.setattr("desk.data.filings.fetch_yahoo", lambda canonical: None)
    code = main(["filings", "NVDA"])
    captured = capsys.readouterr()
    assert code == 1
    assert "FILINGS" not in captured.out
    assert "SEC request failed" in captured.err
    assert "no statements" not in captured.err


def test_latest_fact_prefers_quarter_over_ytd_at_same_end():
    end = "2026-09-30"
    us_gaap = {
        "Revenues": {
            "units": {
                "USD": [
                    {
                        "fp": "Q3",
                        "end": end,
                        "start": "2026-01-01",
                        "val": 900,
                        "filed": "2026-10-01",
                    },
                    {
                        "fp": "Q3",
                        "end": end,
                        "start": "2026-07-01",
                        "val": 90,
                        "filed": "2026-10-01",
                    },
                ]
            }
        }
    }
    frame = _latest_fact(us_gaap, ("Revenues",))
    assert frame is not None
    assert float(frame.iloc[0, 0]) == 90


def test_missing_start_loses_to_a_real_quarter():
    end = "2026-09-30"
    us_gaap = {
        "Revenues": {
            "units": {
                "USD": [
                    {"fp": "Q3", "end": end, "val": 900, "filed": "2026-11-01"},
                    {
                        "fp": "Q3",
                        "end": end,
                        "start": "2026-07-01",
                        "val": 90,
                        "filed": "2026-10-01",
                    },
                ]
            }
        }
    }
    frame = _latest_fact(us_gaap, ("Revenues",))
    assert frame is not None
    assert float(frame.iloc[0, 0]) == 90


def test_instant_facts_follow_the_latest_filing():
    end = "2026-09-30"
    us_gaap = {
        "Assets": {
            "units": {
                "USD": [
                    {"fp": "Q3", "end": end, "val": 1, "filed": "2026-10-01"},
                    {"fp": "Q3", "end": end, "val": 2, "filed": "2026-11-01"},
                ]
            }
        }
    }
    frame = _latest_fact(us_gaap, ("Assets",))
    assert frame is not None
    assert float(frame.iloc[0, 0]) == 2


def test_sec_error_redacts_the_user_agent(monkeypatch, capsys):
    ua = "DeskTestAgent desk-test@example.com"
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", ua)
    monkeypatch.setattr("desk.data.filings.fetch_yahoo", lambda canonical: None)

    class MappingResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"0": {"ticker": "NVDA", "cik_str": 1045810}}

    class FactsResponse:
        text = f"refused for {ua}"

        def raise_for_status(self):
            return None

        def json(self):
            raise requests.exceptions.JSONDecodeError("not json", self.text, 0)

    def fake_get(url, **kwargs):
        if "company_tickers" in url:
            return MappingResponse()
        if "companyfacts" in url:
            return FactsResponse()
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr("desk.data.filings.requests.get", fake_get)
    code = main(["filings", "NVDA"])
    captured = capsys.readouterr()
    assert code == 1
    assert "FILINGS" not in captured.out
    assert ua not in captured.err
    assert captured.err


def _three(frame, period="quarterly"):
    return Statements(income=frame, balance=frame, cashflow=frame, period=period)


def test_yahoo_line_items_are_used_instead_of_sec_cells(monkeypatch):
    def sec_must_not_run(canonical):
        raise AssertionError("sec was called")

    income = pd.DataFrame({"2026-09-30": [11.0], "2026-06-30": [10.0]}, index=["Gross Profit"])
    quarterly = _three(income)
    monkeypatch.setattr("desk.data.filings.fetch_sec", sec_must_not_run)
    monkeypatch.setattr(
        "desk.data.filings.fetch_yahoo",
        lambda canonical: YahooFilings(quarterly, None, None),
    )
    text = load_filings("NVDA")
    assert text.splitlines()[0] == "FILINGS NVDA quarterly yahoo"
    assert "Gross Profit" in text


def test_only_the_four_most_recent_quarter_columns_are_printed():
    dates = ["2026-09-30", "2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30"]
    income = pd.DataFrame({date: [1.0] for date in dates}, index=["Total Revenue"])
    text = filings_text("NVDA", yahoo=_three(income))
    assert "2026-09-30" in text
    assert "2025-12-31" in text
    assert "2025-09-30" not in text


def test_annual_columns_missing_from_the_quarters_are_printed():
    quarterly = _three(pd.DataFrame({"2026-09-30": [1.0]}, index=["Total Revenue"]))
    annual = _three(pd.DataFrame({"2024-12-31": [4242.0]}, index=["Net Income"]), "annual")
    text = filings_text("NVDA", yahoo=quarterly, annual=annual)
    assert text.splitlines()[0] == "FILINGS NVDA quarterly yahoo"
    assert "4242" in text
    assert "Annual Income statement" in text


def test_annual_is_omitted_when_its_columns_are_already_quarterly():
    quarterly = _three(pd.DataFrame({"2025-12-31": [1.0]}, index=["Total Revenue"]))
    annual = _three(pd.DataFrame({"2025-12-31": [9999.0]}, index=["Annual Only Item"]), "annual")
    text = filings_text("NVDA", yahoo=quarterly, annual=annual)
    assert "Annual Only Item" not in text
    assert "9999" not in text


def test_insider_trades_are_printed_with_the_statements():
    insider = pd.DataFrame({"Insider": ["Ada Lovelace"], "Shares": [10]})
    text = filings_text("NVDA", yahoo=_statements(), insider=insider)
    assert "## Insider transactions" in text
    assert "Ada Lovelace" in text


def test_insider_table_keeps_the_fifteen_newest_rows():
    insider = pd.DataFrame(
        {
            "Start Date": pd.date_range("2026-01-01", periods=16, freq="D"),
            "Insider": [f"Person {i}" for i in range(16)],
        }
    )
    text = filings_text("NVDA", yahoo=_statements(), insider=insider)
    assert "Person 15" in text
    assert "Person 0" not in text


def test_invalid_ticker_exits_without_calling_vendors(monkeypatch, capsys):
    def vendor_must_not_run(*_args, **_kwargs):
        raise AssertionError("vendor must not be called")

    monkeypatch.setattr("desk.data.filings.fetch_sec", vendor_must_not_run)
    monkeypatch.setattr("desk.data.filings.fetch_yahoo", vendor_must_not_run)
    code = main(["filings", ".."])
    captured = capsys.readouterr()
    assert code == 1
    assert "FILINGS" not in captured.out
    assert captured.err
