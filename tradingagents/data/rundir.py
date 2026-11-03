"""Prepare one run directory."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from tradingagents.data.errors import TradingAgentsError
from tradingagents.data.symbols import safe_ticker_component


def ticker_path_segment(raw: str) -> str:
    """Path segment for ``.tradingagents/<segment>/``: validate, uppercase ASCII letters only."""
    stripped = raw.strip()
    try:
        safe_ticker_component(stripped)
    except ValueError as exc:
        raise TradingAgentsError(str(exc)) from exc
    return "".join(c.upper() if c.isascii() and c.isalpha() else c for c in stripped)


def prepare_run_dir(
    ticker: str,
    *,
    base: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Create ``.tradingagents/<ticker>/<local-date>/<HHMMSS>/`` under *base*.

    A provided *now* is read as its wall time, with no timezone conversion.
    An existing directory is left in place. The next free suffix is ``-2``
    through ``-99``.
    """
    segment = ticker_path_segment(ticker)
    moment = now if now is not None else datetime.now()
    day = moment.date().isoformat()
    stamp = f"{moment.hour:02d}{moment.minute:02d}{moment.second:02d}"
    root = (base or Path.cwd()).resolve() / ".tradingagents" / segment / day
    names = [stamp, *[f"{stamp}-{n}" for n in range(2, 100)]]
    for name in names:
        run_dir = root / name
        if not run_dir.exists():
            run_dir.mkdir(parents=True)
            return run_dir.resolve()
    raise TradingAgentsError(
        f"no free run directory for {segment} on {day} from {stamp} through {stamp}-99"
    )
