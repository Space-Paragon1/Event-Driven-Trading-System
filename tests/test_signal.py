"""Tests for SignalGenerator."""

from __future__ import annotations

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, MarketDataEvent, SignalEvent
from trading.market_data.feed import MarketDataFeed
from trading.signal.generator import SignalGenerator


def _run_pipeline(n_ticks: int, seed: int = 0) -> list[SignalEvent]:
    bus = EventBus()
    signals: list[SignalEvent] = []
    bus.subscribe(SignalEvent, signals.append)

    SignalGenerator(seed=seed).register(bus)
    MarketDataFeed(symbol="X", n_ticks=n_ticks, seed=seed).emit(bus)
    bus.run()
    return signals


def test_one_signal_per_market_data_event() -> None:
    signals = _run_pipeline(n_ticks=8)
    assert len(signals) == 8


def test_signal_direction_is_valid_enum() -> None:
    signals = _run_pipeline(n_ticks=30, seed=42)
    valid = {Direction.BUY, Direction.SELL, Direction.HOLD}
    assert all(s.direction in valid for s in signals)


def test_signal_strength_in_range() -> None:
    signals = _run_pipeline(n_ticks=30, seed=42)
    assert all(0.0 <= s.strength <= 1.0 for s in signals)


def test_signal_symbol_matches_feed() -> None:
    bus = EventBus()
    signals: list[SignalEvent] = []
    bus.subscribe(SignalEvent, signals.append)
    SignalGenerator().register(bus)
    MarketDataFeed(symbol="GOOGL", n_ticks=5).emit(bus)
    bus.run()
    assert all(s.symbol == "GOOGL" for s in signals)


def test_all_directions_appear_over_many_ticks() -> None:
    """With enough ticks the random generator should hit every direction."""
    signals = _run_pipeline(n_ticks=300, seed=1)
    directions = {s.direction for s in signals}
    assert directions == {Direction.BUY, Direction.SELL, Direction.HOLD}
