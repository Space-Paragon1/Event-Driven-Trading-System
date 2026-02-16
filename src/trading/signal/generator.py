"""Signal generator — produces random BUY / SELL / HOLD signals."""

from __future__ import annotations

import random

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, MarketDataEvent, SignalEvent


class SignalGenerator:
    """Subscribes to :class:`~trading.events.types.MarketDataEvent` and emits
    a random :class:`~trading.events.types.SignalEvent` for each bar.

    Direction is chosen uniformly from BUY / SELL / HOLD.
    Strength is a random float in ``[0.0, 1.0]``.

    Args:
        seed: Optional RNG seed for reproducible output.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._bus: EventBus | None = None
        self._rng = random.Random(seed)

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(MarketDataEvent, self._on_market_data)

    # ------------------------------------------------------------------

    def _on_market_data(self, event: MarketDataEvent) -> None:
        assert self._bus is not None, "register() must be called before emitting events"
        direction = self._rng.choice([Direction.BUY, Direction.SELL, Direction.HOLD])
        strength = round(self._rng.random(), 4)
        self._bus.publish(
            SignalEvent(
                symbol=event.symbol,
                timestamp=event.timestamp,
                direction=direction,
                strength=strength,
            )
        )
