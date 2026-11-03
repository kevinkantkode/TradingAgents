from datetime import date

from tradingagents.cli import main
from tradingagents.data.rundir import prepare_run_dir, ticker_path_segment


def test_ticker_path_segment_uppercases_ascii_letters_only():
    assert ticker_path_segment("nvda") == "NVDA"
    assert ticker_path_segment("0700.HK") == "0700.HK"


def test_prepare_run_dir_creates_and_wipes(tmp_path):
    stale = tmp_path / ".tradingagents" / "NVDA" / date.today().isoformat()
    stale.mkdir(parents=True)
    (stale / "bull.md").write_text("old", encoding="utf-8")

    run_dir = prepare_run_dir("nvda", base=tmp_path)

    assert run_dir == stale.resolve()
    assert run_dir.is_dir()
    assert not any(run_dir.iterdir())


def test_run_dir_cli_prints_absolute_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = main(["run-dir", "NVDA"])
    assert code == 0
    line = capsys.readouterr().out.strip()
    assert line == str((tmp_path / ".tradingagents" / "NVDA" / date.today().isoformat()).resolve())


def test_run_dir_rejects_unsafe_ticker():
    assert main(["run-dir", ".."]) == 1
