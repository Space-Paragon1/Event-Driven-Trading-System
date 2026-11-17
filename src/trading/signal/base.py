"""Base class for bar-driven strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, MarketDataEvent, SignalEvent

Signal = tuple[Direction, float]
"""A strategy decision: direction plus a strength in ``[0, 1]``."""

HOLD: Signal = (Direction.HOLD, 0.0)


class Strategy(ABC):
    """Turns bars into signals. Subclasses implement only :meth:`on_bar`.

    The base class subscribes to :class:`MarketDataEvent` and publishes exactly
    one :class:`SignalEvent` per bar, with strength clamped to ``[0, 1]``.
    Strategies see each bar *after* it closes; any order they trigger executes
    on the following bar.

    A minimal strategy::

        class AlwaysLong(Strategy):
            name = "always_long"

            def on_bar(self, bar: MarketDataEvent) -> Signal:
                return Direction.BUY, 1.0
    """

    name: str = "strategy"

    def __init__(self) -> None:
        self._bus: EventBus | None = None

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(MarketDataEvent, self._on_market_data)

    @abstractmethod
    def on_bar(self, bar: MarketDataEvent) -> Signal:
        """Return the signal for *bar*, using only this and earlier bars."""

    def _on_market_data(self, bar: MarketDataEvent) -> None:
        if self._bus is None:
            raise RuntimeError(f"{type(self).__name__}.register() must be called before use")
        direction, strength = self.on_bar(bar)
        self._bus.publish(
            SignalEvent(
                symbol=bar.symbol,
                timestamp=bar.timestamp,
                direction=direction,
                strength=round(min(max(strength, 0.0), 1.0), 6),
            )
        )
