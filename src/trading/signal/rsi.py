"""RSI signal strategy — Relative Strength Index crossover into overbought/oversold zones."""

from __future__ import annotations

from collections import deque

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, MarketDataEvent, SignalEvent


class RSIStrategy:
    """Generates BUY / SELL / HOLD signals using the Relative Strength Index.

    Signal logic (zone-crossing, not just level):

    - **BUY**  when RSI crosses **below** the *oversold* threshold
      (momentum has just become oversold — potential reversal upward).
    - **SELL** when RSI crosses **above** the *overbought* threshold
      (momentum has just become overbought — potential reversal downward).
    - **HOLD** during the warm-up period (fewer than *period* + 1 bars seen)
      or when RSI stays within the neutral zone.

    RSI formula::

        changes  = diff of last (period + 1) closing prices
        avg_gain = mean of positive changes  (0 where change ≤ 0)
        avg_loss = mean of |negative changes| (0 where change ≥ 0)
        RS       = avg_gain / avg_loss   (RSI = 100 when avg_loss == 0)
        RSI      = 100 − (100 / (1 + RS))

    Signal strength::

        strength = abs(rsi − 50) / 50     (normalised distance from midpoint)

    Args:
        period:     Look-back window for RSI calculation (default ``14``).
        overbought: RSI level above which the market is considered overbought
                    (default ``70.0``).
        oversold:   RSI level below which the market is considered oversold
                    (default ``30.0``).
    """

    def __init__(
        self,
        period: int = 14,
        overbought: float = 70.0,
        oversold: float = 30.0,
    ) -> None:
        if period < 2:
            raise ValueError(f"period must be at least 2, got {period}")
        if oversold >= overbought:
            raise ValueError(
                f"oversold ({oversold}) must be less than overbought ({overbought})"
            )
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        self._bus: EventBus | None = None
        # per-symbol rolling price window; need period+1 prices to compute period diffs
        self._prices: dict[str, deque[float]] = {}
        # last RSI value — used for crossover detection
        self._prev_rsi: dict[str, float] = {}

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(MarketDataEvent, self._on_market_data)

    # ------------------------------------------------------------------

    def _on_market_data(self, event: MarketDataEvent) -> None:
        assert self._bus is not None

        sym = event.symbol
        if sym not in self._prices:
            self._prices[sym] = deque(maxlen=self.period + 1)

        self._prices[sym].append(event.close)
        prices = self._prices[sym]

        # Warm-up: not enough data to compute RSI yet
        if len(prices) < self.period + 1:
            self._bus.publish(
                SignalEvent(
                    symbol=sym,
                    timestamp=event.timestamp,
                    direction=Direction.HOLD,
                    strength=0.0,
                )
            )
            return

        # Compute RSI
        price_list = list(prices)
        changes = [price_list[i] - price_list[i - 1] for i in range(1, len(price_list))]
        gains = [c for c in changes if c > 0]
        losses = [abs(c) for c in changes if c < 0]

        avg_gain = sum(gains) / self.period if gains else 0.0
        avg_loss = sum(losses) / self.period if losses else 0.0

        if avg_loss == 0.0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        strength = round(min(abs(rsi - 50.0) / 50.0, 1.0), 6)

        prev_rsi = self._prev_rsi.get(sym)

        if prev_rsi is not None:
            if prev_rsi >= self.oversold and rsi < self.oversold:
                direction = Direction.BUY
            elif prev_rsi <= self.overbought and rsi > self.overbought:
                direction = Direction.SELL
            else:
                direction = Direction.HOLD
        else:
            direction = Direction.HOLD

        self._prev_rsi[sym] = rsi

        self._bus.publish(
            SignalEvent(
                symbol=sym,
                timestamp=event.timestamp,
                direction=direction,
                strength=strength,
            )
        )
