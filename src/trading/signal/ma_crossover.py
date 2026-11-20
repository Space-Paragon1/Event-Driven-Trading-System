"""Moving-average crossover strategy."""

from __future__ import annotations

from collections import defaultdict

from trading.events.types import Direction, MarketDataEvent
from trading.signal.base import HOLD, Signal, Strategy
from trading.signal.indicators import SMA


class MACrossoverStrategy(Strategy):
    """Trend-following SMA crossover.

    - **BUY** on the bar where SMA(*fast*) crosses above SMA(*slow*).
    - **SELL** on the bar where SMA(*fast*) crosses below SMA(*slow*).
    - **HOLD** otherwise, including the warm-up period before *slow* bars.

    Strength is the relative spread between the averages,
    ``|fast - slow| / slow``, clamped to ``[0, 1]``.

    Args:
        fast: Fast SMA window.
        slow: Slow SMA window; must be greater than *fast*.
    """

    name = "ma_crossover"

    def __init__(self, fast: int = 5, slow: int = 20) -> None:
        if fast < 1:
            raise ValueError(f"fast must be at least 1, got {fast}")
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be less than slow ({slow})")
        super().__init__()
        self.fast = fast
        self.slow = slow
        self._fast_sma: defaultdict[str, SMA] = defaultdict(lambda: SMA(fast))
        self._slow_sma: defaultdict[str, SMA] = defaultdict(lambda: SMA(slow))
        self._prev_spread: dict[str, float] = {}

    def on_bar(self, bar: MarketDataEvent) -> Signal:
        fast = self._fast_sma[bar.symbol].update(bar.close)
        slow = self._slow_sma[bar.symbol].update(bar.close)
        if fast is None or slow is None:
            return HOLD

        spread = fast - slow
        prev = self._prev_spread.get(bar.symbol)
        self._prev_spread[bar.symbol] = spread
        strength = abs(spread) / slow if slow else 0.0

        if prev is not None and prev <= 0.0 < spread:
            return Direction.BUY, strength
        if prev is not None and prev >= 0.0 > spread:
            return Direction.SELL, strength
        return Direction.HOLD, strength
