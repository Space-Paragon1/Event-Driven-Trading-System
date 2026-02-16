"""CSV market data feed — replays historical OHLCV data from a CSV file."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from trading.bus.event_bus import EventBus
from trading.events.types import MarketDataEvent


class CSVFeed:
    """Reads a CSV file and emits one :class:`~trading.events.types.MarketDataEvent`
    per row.

    Expected CSV columns (case-insensitive header row required):
    ``date, open, high, low, close, volume``

    Date formats tried in order: ``%Y-%m-%d``, ``%Y-%m-%d %H:%M:%S``,
    ``%m/%d/%Y``.

    Args:
        path:   Path to the CSV file.
        symbol: Ticker symbol to tag events with.
    """

    _DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y")

    def __init__(self, path: str | Path, symbol: str) -> None:
        self.path = Path(path)
        self.symbol = symbol

    # ------------------------------------------------------------------

    def emit(self, bus: EventBus) -> None:
        """Read the CSV and publish all rows to *bus*."""
        with self.path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            # normalise header names to lowercase
            for row in reader:
                normalised = {k.strip().lower(): v.strip() for k, v in row.items()}
                bus.publish(
                    MarketDataEvent(
                        symbol=self.symbol,
                        timestamp=self._parse_date(normalised["date"]),
                        open=float(normalised["open"]),
                        high=float(normalised["high"]),
                        low=float(normalised["low"]),
                        close=float(normalised["close"]),
                        volume=int(float(normalised["volume"])),
                    )
                )

    # ------------------------------------------------------------------

    def _parse_date(self, value: str) -> datetime:
        for fmt in self._DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unrecognised date format: {value!r}")
