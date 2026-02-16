"""Tests for MACrossoverStrategy."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, MarketDataEvent, SignalEvent
from trading.signal.ma_crossover import MACrossoverStrategy

_START = datetime(2024, 1, 2, 9, 30)


def _make_event(symbol: str, close: float, i: int = 0) -> MarketDataEvent:
    return MarketDataEvent(
        symbol=symbol,
        timestamp=_START + timedelta(minutes=i),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
    )


def _run_prices(prices: list[float], fast: int = 3, slow: int = 5) -> list[SignalEvent]:
    bus = EventBus()
    signals: list[SignalEvent] = []
    bus.subscribe(SignalEvent, signals.append)
    MACrossoverStrategy(fast=fast, slow=slow).register(bus)
    for i, p in enumerate(prices):
        bus.publish(_make_event("X", p, i))
    bus.run()
    return signals


def test_hold_during_warmup() -> None:
    # fewer than slow=5 bars → all HOLD
    signals = _run_prices([100.0, 101.0, 102.0, 103.0])
    assert all(s.direction is Direction.HOLD for s in signals)


def test_buy_on_upward_crossover() -> None:
    # fast=3, slow=5
    # build a sequence where fast crosses above slow
    # declining prices (fast < slow), then a spike up
    prices = [100.0, 99.0, 98.0, 97.0, 96.0,   # slow warm-up, all declining
              110.0, 120.0, 130.0]               # spike — fast will cross above
    signals = _run_prices(prices, fast=3, slow=5)
    directions = [s.direction for s in signals]
    assert Direction.BUY in directions


def test_sell_on_downward_crossover() -> None:
    prices = [100.0, 101.0, 102.0, 103.0, 104.0,  # warm-up, rising
              80.0, 60.0, 40.0]                    # sharp drop — fast crosses below
    signals = _run_prices(prices, fast=3, slow=5)
    directions = [s.direction for s in signals]
    assert Direction.SELL in directions


def test_strength_in_range() -> None:
    prices = [float(i) for i in range(1, 30)]
    signals = _run_prices(prices, fast=3, slow=5)
    for s in signals:
        assert 0.0 <= s.strength


def test_one_signal_per_bar() -> None:
    prices = [float(i) for i in range(1, 20)]
    signals = _run_prices(prices)
    assert len(signals) == len(prices)


def test_invalid_fast_slow_raises() -> None:
    with pytest.raises(ValueError):
        MACrossoverStrategy(fast=10, slow=5)


def test_symbol_preserved() -> None:
    bus = EventBus()
    signals: list[SignalEvent] = []
    bus.subscribe(SignalEvent, signals.append)
    MACrossoverStrategy(fast=2, slow=3).register(bus)
    for i in range(5):
        bus.publish(_make_event("TSLA", 100.0 + i, i))
    bus.run()
    assert all(s.symbol == "TSLA" for s in signals)
