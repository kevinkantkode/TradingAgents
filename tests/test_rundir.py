import re
from datetime import date, datetime
from pathlib import Path

import pytest

from tradingagents.cli import main
from tradingagents.data.errors import TradingAgentsError
from tradingagents.data.rundir import prepare_run_dir, ticker_path_segment


def test_ticker_path_segment_uppercases_ascii_letters_only():
    assert ticker_path_segment("nvda") == "NVDA"
    assert ticker_path_segment("0700.HK") == "0700.HK"


def test_prepare_run_dir_keeps_the_earlier_run(tmp_path):
    moment = datetime(2026, 11, 3, 23, 1, 55)
    first = prepare_run_dir("nvda", base=tmp_path, now=moment)
    (first / "bull.md").write_text("old", encoding="utf-8")

    second = prepare_run_dir("nvda", base=tmp_path, now=moment)

    assert first == (tmp_path / ".tradingagents" / "NVDA" / "2026-11-03" / "230155").resolve()
    assert (first / "bull.md").read_text(encoding="utf-8") == "old"
    assert second == first.parent / "230155-2"
    assert second.is_dir()
    assert not any(second.iterdir())


def test_prepare_run_dir_third_call_uses_the_next_suffix(tmp_path):
    moment = datetime(2026, 11, 3, 23, 1, 55)
    prepare_run_dir("NVDA", base=tmp_path, now=moment)
    prepare_run_dir("NVDA", base=tmp_path, now=moment)
    third = prepare_run_dir("NVDA", base=tmp_path, now=moment)
    assert third.name == "230155-3"


def test_prepare_run_dir_stops_at_suffix_99(tmp_path):
    moment = datetime(2026, 11, 3, 23, 1, 55)
    day = tmp_path / ".tradingagents" / "NVDA" / "2026-11-03"
    day.mkdir(parents=True)
    (day / "230155").mkdir()
    for n in range(2, 100):
        (day / f"230155-{n}").mkdir()

    with pytest.raises(TradingAgentsError, match="230155-99"):
        prepare_run_dir("NVDA", base=tmp_path, now=moment)

    assert not (day / "230155-100").exists()


def test_run_dir_cli_prints_absolute_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = main(["run-dir", "NVDA"])
    assert code == 0
    line = capsys.readouterr().out.strip()
    path = Path(line)
    assert path.is_absolute()
    assert path.parent.parent == (tmp_path / ".tradingagents" / "NVDA").resolve()
    assert path.parent.name == date.today().isoformat()
    assert re.fullmatch(r"\d{6}", path.name)


def test_run_dir_rejects_unsafe_ticker():
    assert main(["run-dir", ".."]) == 1
