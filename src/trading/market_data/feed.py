"""Feed protocol and a reproducible synthetic data source."""

from __future__ import annotations

import math
import random
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Protocol

from trading.events.types import MarketDataEvent

TRADING_DAYS_PER_YEAR = 252


class Feed(Protocol):
    """A source of bars for one symbol, iterated in chronological order.

    Feeds do not touch the bus: the backtest engine pulls one bar at a time and
    lets the full event cascade settle before requesting the next. That is what
    keeps the simulation causal.
    """

    symbol: str

    def __iter__(self) -> Iterator[MarketDataEvent]: ...


class SyntheticFeed:
    """Daily OHLCV bars from a geometric Brownian motion.

    Prices follow ``dS/S = mu dt + sigma dW`` sampled once per business day,
    with a small overnight gap between the previous close and the next open.
    Fully deterministic for a given *seed*, which makes it ideal for tests and
    reproducible demos. It is not a model of any real instrument.

    Args:
        symbol:             Ticker to tag bars with.
        n_bars:             Number of bars to generate.
        seed:               RNG seed (``None`` = nondeterministic).
        start_price:        Price before the first bar.
        annual_drift:       Expected annual log-return ``mu``.
        annual_volatility:  Annualised volatility ``sigma``.
        start:              Date of the first bar (rolled forward past weekends).
    """

    def __init__(
        self,
        symbol: str,
        n_bars: int = TRADING_DAYS_PER_YEAR,
        seed: int | None = None,
        start_price: float = 150.0,
        annual_drift: float = 0.08,
        annual_volatility: float = 0.25,
        start: datetime = datetime(2024, 1, 2),
    ) -> None:
        if n_bars < 0:
            raise ValueError(f"n_bars must be non-negative, got {n_bars}")
        if start_price <= 0:
            raise ValueError(f"start_price must be positive, got {start_price}")
        if annual_volatility < 0:
            raise ValueError(f"annual_volatility must be non-negative, got {annual_volatility}")
        self.symbol = symbol
        self.n_bars = n_bars
        self.seed = seed
        self.start_price = start_price
        self.annual_drift = annual_drift
        self.annual_volatility = annual_volatility
        self.start = start

    def __iter__(self) -> Iterator[MarketDataEvent]:
        rng = random.Random(self.seed)
        sigma = self.annual_volatility / math.sqrt(TRADING_DAYS_PER_YEAR)
        mu = self.annual_drift / TRADING_DAYS_PER_YEAR
        prev_close = self.start_price
        day = _roll_to_weekday(self.start)

        for _ in range(self.n_bars):
            open_ = round(prev_close * math.exp(rng.gauss(0.0, sigma * 0.25)), 2)
            close = round(open_ * math.exp(mu - 0.5 * sigma**2 + rng.gauss(0.0, sigma)), 2)
            high = round(max(open_, close) * math.exp(abs(rng.gauss(0.0, sigma * 0.5))), 2)
            low = round(min(open_, close) * math.exp(-abs(rng.gauss(0.0, sigma * 0.5))), 2)
            volume = int(1_000_000 * math.exp(rng.gauss(0.0, 0.25)))
            yield MarketDataEvent(
                symbol=self.symbol,
                timestamp=day,
                open=open_,
                high=high,
                low=max(low, 0.01),
                close=close,
                volume=volume,
            )
            prev_close = close
            day = _roll_to_weekday(day + timedelta(days=1))


def _roll_to_weekday(day: datetime) -> datetime:
    while day.weekday() >= 5:  # Saturday = 5, Sunday = 6
        day += timedelta(days=1)
    return day
