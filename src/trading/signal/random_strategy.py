"""Random baseline strategy."""

from __future__ import annotations

import random

from trading.events.types import Direction, MarketDataEvent
from trading.signal.base import Signal, Strategy

_CHOICES = (Direction.BUY, Direction.SELL, Direction.HOLD)


class RandomStrategy(Strategy):
    """Uniformly random BUY / SELL / HOLD with random strength.

    Useful as a null baseline: a real strategy that cannot beat this after
    costs has no edge.

    Args:
        seed: RNG seed for reproducible output.
    """

    name = "random"

    def __init__(self, seed: int | None = None) -> None:
        super().__init__()
        self._rng = random.Random(seed)

    def on_bar(self, bar: MarketDataEvent) -> Signal:
        return self._rng.choice(_CHOICES), self._rng.random()
