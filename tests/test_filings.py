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
