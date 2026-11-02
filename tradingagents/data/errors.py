class TradingAgentsError(Exception):
    """A command cannot do its job. The CLI prints this and exits 1."""


class NoMarketDataError(TradingAgentsError):
    """The vendor returned no usable rows."""


class VendorUnavailableError(TradingAgentsError):
    """The vendor request failed. This says nothing about the instrument."""
