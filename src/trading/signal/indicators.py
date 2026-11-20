"""Incremental technical indicators.

Each ``update()`` consumes one value and returns ``None`` until the indicator has warmed up.
"""

from __future__ import annotations

import math
from collections import deque


class SMA:
    """Simple moving average over the last *period* values."""

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError(f"period must be at least 1, got {period}")
        self.period = period
        self._window: deque[float] = deque(maxlen=period)

    def update(self, value: float) -> float | None:
        self._window.append(value)
        if len(self._window) < self.period:
            return None
        return math.fsum(self._window) / self.period


class RSI:
    """Relative Strength Index with Wilder's smoothing (the standard definition).

    The first value is produced after ``period + 1`` prices, seeded with the
    simple average gain/loss over the first *period* changes. Subsequent
    values use Wilder's recursive average::

        avg = (prev_avg * (period - 1) + current) / period
        RSI = 100 - 100 / (1 + avg_gain / avg_loss)

    A window with no movement at all reads as a neutral 50.
    """

    def __init__(self, period: int = 14) -> None:
        if period < 2:
            raise ValueError(f"period must be at least 2, got {period}")
        self.period = period
        self._prev_price: float | None = None
        self._seed_gains: list[float] = []
        self._seed_losses: list[float] = []
        self._avg_gain: float | None = None
        self._avg_loss: float = 0.0

    def update(self, price: float) -> float | None:
        if self._prev_price is None:
            self._prev_price = price
            return None

        change = price - self._prev_price
        self._prev_price = price
        gain, loss = max(change, 0.0), max(-change, 0.0)

        if self._avg_gain is None:
            self._seed_gains.append(gain)
            self._seed_losses.append(loss)
            if len(self._seed_gains) < self.period:
                return None
            self._avg_gain = math.fsum(self._seed_gains) / self.period
            self._avg_loss = math.fsum(self._seed_losses) / self.period
        else:
            n = self.period
            self._avg_gain = (self._avg_gain * (n - 1) + gain) / n
            self._avg_loss = (self._avg_loss * (n - 1) + loss) / n

        if self._avg_loss == 0.0:
            return 50.0 if self._avg_gain == 0.0 else 100.0
        rs = self._avg_gain / self._avg_loss
        return 100.0 - 100.0 / (1.0 + rs)
