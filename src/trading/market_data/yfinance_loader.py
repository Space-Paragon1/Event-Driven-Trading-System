"""Yahoo Finance data feed — downloads real historical OHLCV bars."""

from __future__ import annotations

import math
from collections.abc import Iterator

from trading.errors import DataError, MissingDependencyError
from trading.events.types import MarketDataEvent


class YFinanceFeed:
    """Downloads split/dividend-adjusted bars from Yahoo Finance via ``yfinance``.

    Data is fetched lazily on first iteration. Rows with missing values are
    dropped.

    Args:
        symbol:   Ticker symbol (e.g. ``"AAPL"``).
        start:    First date, ``YYYY-MM-DD`` (inclusive).
        end:      Last date, ``YYYY-MM-DD`` (exclusive, as in ``yfinance``).
        interval: Bar interval accepted by ``yfinance`` (``"1d"``, ``"1wk"``, ``"1h"`` …).

    Raises:
        MissingDependencyError: if ``yfinance`` is not installed.
        DataError: if the download returns no data.
    """

    def __init__(self, symbol: str, start: str, end: str, interval: str = "1d") -> None:
        self.symbol = symbol
        self.start = start
        self.end = end
        self.interval = interval

    def __iter__(self) -> Iterator[MarketDataEvent]:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise MissingDependencyError("yfinance", "data") from exc

        data = yf.download(
            self.symbol,
            start=self.start,
            end=self.end,
            interval=self.interval,
            progress=False,
            auto_adjust=True,
        )
        if data is None or data.empty:
            raise DataError(
                f"Yahoo Finance returned no data for {self.symbol} "
                f"({self.start} to {self.end}, interval {self.interval})"
            )

        # Recent yfinance versions return (field, ticker) MultiIndex columns
        # even for a single ticker; keep just the field names.
        if getattr(data.columns, "nlevels", 1) > 1:
            data.columns = data.columns.get_level_values(0)

        for ts, row in data.iterrows():
            values = [row["Open"], row["High"], row["Low"], row["Close"], row["Volume"]]
            if any(_is_missing(v) for v in values):
                continue
            yield MarketDataEvent(
                symbol=self.symbol,
                timestamp=ts.to_pydatetime().replace(tzinfo=None),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            )


def _is_missing(value: object) -> bool:
    try:
        return math.isnan(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
