"""RSI mean-reversion strategy."""

from __future__ import annotations

from collections import defaultdict

from trading.events.types import Direction, MarketDataEvent
from trading.signal.base import HOLD, Signal, Strategy
from trading.signal.indicators import RSI


class RSIStrategy(Strategy):
    """Mean reversion on Wilder's RSI zone crossings.

    - **BUY** on the bar where RSI crosses *below* ``oversold``.
    - **SELL** on the bar where RSI crosses *above* ``overbought``.
    - **HOLD** otherwise, including the ``period + 1``-bar warm-up.

    Strength is the distance from the neutral midpoint, ``|RSI - 50| / 50``.

    Args:
        period:     RSI look-back.
        overbought: Upper threshold (0–100).
        oversold:   Lower threshold (0–100); must be below *overbought*.
    """

    name = "rsi"

    def __init__(self, period: int = 14, overbought: float = 70.0, oversold: float = 30.0) -> None:
        if period < 2:
            raise ValueError(f"period must be at least 2, got {period}")
        if not 0.0 <= oversold < overbought <= 100.0:
            raise ValueError(
                f"need 0 <= oversold < overbought <= 100, got oversold={oversold}, "
                f"overbought={overbought}"
            )
        super().__init__()
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        self._rsi: defaultdict[str, RSI] = defaultdict(lambda: RSI(period))
        self._prev_rsi: dict[str, float] = {}

    def on_bar(self, bar: MarketDataEvent) -> Signal:
        rsi = self._rsi[bar.symbol].update(bar.close)
        if rsi is None:
            return HOLD

        prev = self._prev_rsi.get(bar.symbol)
        self._prev_rsi[bar.symbol] = rsi
        strength = abs(rsi - 50.0) / 50.0

        if prev is not None and prev >= self.oversold > rsi:
            return Direction.BUY, strength
        if prev is not None and prev <= self.overbought < rsi:
            return Direction.SELL, strength
        return Direction.HOLD, strength
