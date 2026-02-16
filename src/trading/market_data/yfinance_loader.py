"""Yahoo Finance data feed — downloads real OHLCV bars and emits them onto the bus."""

from __future__ import annotations

from pathlib import Path

from trading.bus.event_bus import EventBus
from trading.events.types import MarketDataEvent


class YFinanceFeed:
    """Fetches historical OHLCV data from Yahoo Finance and publishes one
    :class:`~trading.events.types.MarketDataEvent` per bar.

    Mirrors the :class:`~trading.market_data.csv_loader.CSVFeed` interface —
    call :meth:`emit` once to push all bars onto the bus.

    Args:
        symbol:   Ticker symbol (e.g. ``"AAPL"``).
        start:    Start date string in ``YYYY-MM-DD`` format.
        end:      End date string in ``YYYY-MM-DD`` format (exclusive).
        interval: Bar interval accepted by ``yfinance`` (default ``"1d"``).
                  Common values: ``"1d"``, ``"1wk"``, ``"1mo"``.
    """

    def __init__(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> None:
        self.symbol = symbol
        self.start = start
        self.end = end
        self.interval = interval

    # ------------------------------------------------------------------

    def emit(self, bus: EventBus) -> None:
        """Download data and publish one :class:`MarketDataEvent` per bar."""
        import yfinance as yf  # lazy import — keeps startup fast if not used

        data = yf.download(
            self.symbol,
            start=self.start,
            end=self.end,
            interval=self.interval,
            progress=False,
            auto_adjust=True,
        )

        if data.empty:
            return

        # yfinance may return a MultiIndex when downloading a single ticker;
        # flatten to a simple column index if needed.
        if hasattr(data.columns, "levels"):
            data.columns = data.columns.get_level_values(0)

        for ts, row in data.iterrows():
            bus.publish(
                MarketDataEvent(
                    symbol=self.symbol,
                    timestamp=ts.to_pydatetime().replace(tzinfo=None),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                )
            )
