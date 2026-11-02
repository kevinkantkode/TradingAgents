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
