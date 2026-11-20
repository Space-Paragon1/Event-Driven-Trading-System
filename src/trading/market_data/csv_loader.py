"""CSV market data feed — replays historical OHLCV bars from a file."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from trading.errors import DataError
from trading.events.types import MarketDataEvent

_REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")
_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y")


class CSVFeed:
    """Yields one :class:`MarketDataEvent` per row of a CSV file.

    The file needs a header row with (case-insensitive) columns
    ``date, open, high, low, close, volume``; extra columns are ignored. Rows
    must be in strictly ascending date order. A feed that silently reorders or
    deduplicates data hides problems, so out-of-order rows raise instead.

    Date formats accepted: ``YYYY-MM-DD``, ``YYYY-MM-DD HH:MM:SS``,
    ``YYYY-MM-DDTHH:MM:SS`` and ``MM/DD/YYYY``.

    Args:
        path:   Path to the CSV file.
        symbol: Ticker symbol to tag events with.

    Raises:
        DataError: on a missing file, missing columns, unparseable values or
            out-of-order rows (raised during iteration).
    """

    def __init__(self, path: str | Path, symbol: str) -> None:
        self.path = Path(path)
        self.symbol = symbol

    def __iter__(self) -> Iterator[MarketDataEvent]:
        try:
            fh = self.path.open(newline="")
        except OSError as exc:
            raise DataError(f"cannot open CSV file {self.path}: {exc.strerror}") from exc

        with fh:
            reader = csv.DictReader(fh)
            header = {name.strip().lower() for name in reader.fieldnames or ()}
            missing = [col for col in _REQUIRED_COLUMNS if col not in header]
            if missing:
                raise DataError(f"{self.path}: missing required column(s): {', '.join(missing)}")

            previous: datetime | None = None
            for line_no, raw in enumerate(reader, start=2):
                row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
                if not any(row.values()):
                    continue  # tolerate blank lines
                try:
                    bar = MarketDataEvent(
                        symbol=self.symbol,
                        timestamp=_parse_date(row["date"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(float(row["volume"])),
                    )
                except ValueError as exc:
                    raise DataError(f"{self.path}:{line_no}: {exc}") from exc

                if previous is not None and bar.timestamp <= previous:
                    raise DataError(
                        f"{self.path}:{line_no}: rows must be in ascending date order "
                        f"({bar.timestamp:%Y-%m-%d} follows {previous:%Y-%m-%d})"
                    )
                previous = bar.timestamp
                yield bar


def _parse_date(value: str) -> datetime:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognised date format: {value!r}")
