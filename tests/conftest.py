"""Keep the desk ledger out of the developer's home directory."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_ledger(monkeypatch, tmp_path):
    monkeypatch.setattr("desk.data.ledger.LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
