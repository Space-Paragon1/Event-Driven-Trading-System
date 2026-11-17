"""Tests for RandomStrategy, the Strategy base class and the registry."""

from __future__ import annotations

import pytest

from tests.factories import Capture, bar, publish_all
from trading.bus.event_bus import EventBus
from trading.config import StrategyConfig
from trading.events.types import Direction, MarketDataEvent, SignalEvent
from trading.market_data.feed import SyntheticFeed
from trading.signal.base import Signal, Strategy
from trading.signal.ma_crossover import MACrossoverStrategy
from trading.signal.random_strategy import RandomStrategy
from trading.signal.registry import STRATEGIES, build_strategy
from trading.signal.rsi import RSIStrategy


def _random_signals(n_bars: int, seed: int = 0) -> list[SignalEvent]:
    bus = EventBus()
    RandomStrategy(seed=seed).register(bus)
    cap = Capture(bus, SignalEvent)
    publish_all(bus, *SyntheticFeed("X", n_bars=n_bars, seed=seed))
    return cap[SignalEvent]


def test_random_one_signal_per_bar() -> None:
    assert len(_random_signals(8)) == 8


def test_random_is_reproducible() -> None:
    assert _random_signals(50, seed=3) == _random_signals(50, seed=3)


def test_random_hits_every_direction() -> None:
    assert {s.direction for s in _random_signals(300, seed=1)} == set(Direction)


def test_random_strength_in_unit_interval() -> None:
    assert all(0.0 <= s.strength <= 1.0 for s in _random_signals(50, seed=42))


def test_base_class_clamps_strength() -> None:
    class Loud(Strategy):
        def on_bar(self, bar: MarketDataEvent) -> Signal:
            return Direction.BUY, 7.5

    bus = EventBus()
    Loud().register(bus)
    cap = Capture(bus, SignalEvent)
    publish_all(bus, bar(1.0))
    assert cap[SignalEvent][0].strength == 1.0


@pytest.mark.parametrize(
    ("name", "cls"),
    [("ma_crossover", MACrossoverStrategy), ("rsi", RSIStrategy), ("random", RandomStrategy)],
)
def test_registry_builds_each_strategy(name: str, cls: type) -> None:
    strategy = build_strategy(StrategyConfig(type=name))
    assert isinstance(strategy, cls)
    assert strategy.name == name


def test_registry_passes_parameters() -> None:
    s = build_strategy(StrategyConfig(type="ma_crossover", fast_period=3, slow_period=9))
    assert isinstance(s, MACrossoverStrategy)
    assert (s.fast, s.slow) == (3, 9)


def test_registry_names_are_stable() -> None:
    assert set(STRATEGIES) == {"ma_crossover", "rsi", "random"}
