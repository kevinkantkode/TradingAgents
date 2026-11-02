"""Prepare the gitignored directory for one Cursor desk run."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from desk.data.errors import DeskError
from desk.data.symbols import safe_ticker_component


def ticker_path_segment(raw: str) -> str:
    """Path segment for ``.desk/<segment>/``: validate, uppercase ASCII letters only."""
    stripped = raw.strip()
    try:
        safe_ticker_component(stripped)
    except ValueError as exc:
        raise DeskError(str(exc)) from exc
    return "".join(c.upper() if c.isascii() and c.isalpha() else c for c in stripped)


def prepare_run_dir(ticker: str, *, base: Path | None = None) -> Path:
    """Create ``.desk/<ticker>/<local-date>/`` under *base* (default cwd), wiping if present."""
    segment = ticker_path_segment(ticker)
    run_dir = (base or Path.cwd()).resolve() / ".desk" / segment / date.today().isoformat()
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    return run_dir.resolve()
