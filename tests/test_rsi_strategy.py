"""Tests for RSIStrategy."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, MarketDataEvent, SignalEvent
from trading.signal.rsi import RSIStrategy

_BASE_TS = datetime(2024, 1, 2, 9, 30)


def _make_event(close: float, i: int = 0) -> MarketDataEvent:
    return MarketDataEvent(
        symbol="AAPL",
        timestamp=_BASE_TS + timedelta(days=i),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1_000_000,
    )


def _run_prices(prices: list[float], period: int = 14,
                overbought: float = 70.0, oversold: float = 30.0) -> list[SignalEvent]:
    bus = EventBus()
    signals: list[SignalEvent] = []
    bus.subscribe(SignalEvent, signals.append)
    RSIStrategy(period=period, overbought=overbought, oversold=oversold).register(bus)
    for i, p in enumerate(prices):
        bus.publish(_make_event(p, i))
    bus.run()
    return signals


def test_hold_during_warmup() -> None:
    # With period=5 we need 6 prices; send only 5
    signals = _run_prices([100.0] * 5, period=5)
    assert len(signals) == 5
    assert all(s.direction is Direction.HOLD for s in signals)


def test_hold_in_neutral_zone() -> None:
    # Flat prices → RSI = 100 (all gains, no losses after first) or 50;
    # either way, no zone crossing → HOLD
    signals = _run_prices([100.0] * 20, period=5)
    assert all(s.direction is Direction.HOLD for s in signals)


def test_buy_signal_on_oversold_crossover() -> None:
    # Build a price series that pushes RSI below 30, then recover
    # Sharp drop followed by a rise triggers oversold crossover → BUY
    prices = [100.0] * 6 + [80.0, 70.0, 60.0, 55.0, 50.0] + [55.0, 60.0, 65.0]
    signals = _run_prices(prices, period=5, oversold=30.0, overbought=70.0)
    directions = [s.direction for s in signals]
    assert Direction.BUY in directions


def test_sell_signal_on_overbought_crossover() -> None:
    # Start with a declining series so RSI is below 70, then a sharp rise
    # crosses RSI above 70 → SELL crossover.
    # With period=5 (deque maxlen=6):
    #   prices [100..90] → all declines, RSI=0 on 6th bar (first computed)
    #   prices [95, 103, 115] → RSI climbs from ~38 → ~68 → ~86 (crosses 70)
    prices = [100.0, 98.0, 96.0, 94.0, 92.0, 90.0, 95.0, 103.0, 115.0]
    signals = _run_prices(prices, period=5, oversold=30.0, overbought=70.0)
    directions = [s.direction for s in signals]
    assert Direction.SELL in directions


def test_strength_in_range() -> None:
    prices = list(range(100, 130))
    signals = _run_prices(prices, period=5)
    for s in signals:
        assert 0.0 <= s.strength <= 1.0


def test_raises_if_period_too_small() -> None:
    with pytest.raises(ValueError):
        RSIStrategy(period=1)
