"""Market data feed — emits synthetic OHLCV ticks."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from trading.bus.event_bus import EventBus
from trading.events.types import MarketDataEvent

_BASE_PRICE = 150.0
_BASE_VOLUME = 1_000_000


class MarketDataFeed:
    """Generates *n_ticks* synthetic OHLCV bars for *symbol* and publishes
    them to the bus via :meth:`emit`.

    Price evolves as a simple random walk; volume is randomly varied around
    a base level.  This is purely for pipeline wiring — no statistical
    realism is intended.

    Args:
        symbol:  Ticker symbol (e.g. ``"AAPL"``).
        n_ticks: Number of bars to emit.
        seed:    Optional RNG seed for reproducible output.
    """

    def __init__(
        self,
        symbol: str,
        n_ticks: int = 10,
        seed: int | None = None,
    ) -> None:
        self.symbol = symbol
        self.n_ticks = n_ticks
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------

    def emit(self, bus: EventBus) -> None:
        """Publish all ticks to *bus* (does not call ``bus.run()``)."""
        price = _BASE_PRICE
        start = datetime(2024, 1, 2, 9, 30, 0)

        for i in range(self.n_ticks):
            change = self._rng.uniform(-1.0, 1.0)
            open_ = round(price, 2)
            close = round(max(0.01, price + change), 2)
            high = round(max(open_, close) + self._rng.uniform(0.0, 0.5), 2)
            low = round(min(open_, close) - self._rng.uniform(0.0, 0.5), 2)
            volume = int(_BASE_VOLUME * self._rng.uniform(0.8, 1.2))
            timestamp = start + timedelta(minutes=i)

            bus.publish(
                MarketDataEvent(
                    symbol=self.symbol,
                    timestamp=timestamp,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
            price = close
