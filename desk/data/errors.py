class DeskError(Exception):
    """A command cannot do its job. The CLI prints this and exits 1."""


class NoMarketDataError(DeskError):
    """The vendor returned no usable rows."""


class VendorUnavailableError(DeskError):
    """The vendor request failed. This says nothing about the instrument."""
