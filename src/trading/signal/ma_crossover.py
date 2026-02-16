"""MA Crossover signal strategy — SMA fast/slow crossover."""

from __future__ import annotations

from collections import deque

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, MarketDataEvent, SignalEvent


class MACrossoverStrategy:
    """Generates BUY / SELL / HOLD signals based on a simple moving average
    crossover of two windows: *fast* and *slow*.

    Logic:
    - **BUY**  when SMA(fast) crosses above SMA(slow) (upward crossover).
    - **SELL** when SMA(fast) crosses below SMA(slow) (downward crossover).
    - **HOLD** otherwise, or during the warm-up period (fewer than *slow*
      bars seen).

    Signal strength is the normalised distance between the two SMAs::

        strength = abs(sma_fast - sma_slow) / sma_slow

    Args:
        fast: Look-back window for the fast SMA (default ``5``).
        slow: Look-back window for the slow SMA (default ``20``).
    """

    def __init__(self, fast: int = 5, slow: int = 20) -> None:
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be less than slow ({slow})")
        self.fast = fast
        self.slow = slow
        self._bus: EventBus | None = None
        # per-symbol price history — only keep as many bars as needed
        self._prices: dict[str, deque[float]] = {}
        # previous SMA values for crossover detection
        self._prev_fast: dict[str, float] = {}
        self._prev_slow: dict[str, float] = {}

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(MarketDataEvent, self._on_market_data)

    # ------------------------------------------------------------------

    def _on_market_data(self, event: MarketDataEvent) -> None:
        assert self._bus is not None

        sym = event.symbol
        if sym not in self._prices:
            self._prices[sym] = deque(maxlen=self.slow)

        self._prices[sym].append(event.close)
        prices = self._prices[sym]

        if len(prices) < self.slow:
            # warm-up: not enough data yet
            self._bus.publish(
                SignalEvent(
                    symbol=sym,
                    timestamp=event.timestamp,
                    direction=Direction.HOLD,
                    strength=0.0,
                )
            )
            return

        sma_fast = sum(list(prices)[-self.fast :]) / self.fast
        sma_slow = sum(prices) / self.slow
        strength = round(abs(sma_fast - sma_slow) / sma_slow, 6) if sma_slow else 0.0

        prev_fast = self._prev_fast.get(sym)
        prev_slow = self._prev_slow.get(sym)

        if prev_fast is not None and prev_slow is not None:
            if prev_fast <= prev_slow and sma_fast > sma_slow:
                direction = Direction.BUY
            elif prev_fast >= prev_slow and sma_fast < sma_slow:
                direction = Direction.SELL
            else:
                direction = Direction.HOLD
        else:
            direction = Direction.HOLD

        self._prev_fast[sym] = sma_fast
        self._prev_slow[sym] = sma_slow

        self._bus.publish(
            SignalEvent(
                symbol=sym,
                timestamp=event.timestamp,
                direction=direction,
                strength=strength,
            )
        )
