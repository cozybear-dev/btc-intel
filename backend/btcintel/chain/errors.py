"""Errors raised by chain data access."""


class ChainError(Exception):
    """Base class for chain data access errors."""


class NotFound(ChainError):
    """The requested transaction/address does not exist (HTTP 404/400 from the backend)."""


class SourceError(ChainError):
    """A backend failed (network, 5xx, repeated 429, unexpected status) or all backends failed."""
