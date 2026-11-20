"""Exception hierarchy: everything the package raises on purpose is a :class:`TradingError`."""

from __future__ import annotations


class TradingError(Exception):
    """Base class for all errors raised by this package."""


class ConfigError(TradingError, ValueError):
    """Invalid or inconsistent configuration."""


class DataError(TradingError):
    """Market data is missing, malformed, or could not be fetched."""


class MissingDependencyError(TradingError, ImportError):
    """An optional dependency needed for the requested feature is not installed."""

    def __init__(self, package: str, extra: str) -> None:
        super().__init__(
            f"{package!r} is required for this feature. "
            f"Install it with: pip install 'event-driven-trading-system[{extra}]'"
        )
