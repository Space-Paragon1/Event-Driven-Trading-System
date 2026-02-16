"""Tests for MarketDataFeed."""

from __future__ import annotations

from trading.bus.event_bus import EventBus
from trading.events.types import MarketDataEvent
from trading.market_data.feed import MarketDataFeed


def _collect_events(n_ticks: int, seed: int = 0) -> list[MarketDataEvent]:
    bus = EventBus()
    events: list[MarketDataEvent] = []
    bus.subscribe(MarketDataEvent, events.append)
    feed = MarketDataFeed(symbol="TEST", n_ticks=n_ticks, seed=seed)
    feed.emit(bus)
    bus.run()
    return events


def test_feed_emits_correct_number_of_ticks() -> None:
    events = _collect_events(n_ticks=5)
    assert len(events) == 5


def test_feed_emits_correct_symbol() -> None:
    bus = EventBus()
    events: list[MarketDataEvent] = []
    bus.subscribe(MarketDataEvent, events.append)
    MarketDataFeed(symbol="MSFT", n_ticks=3, seed=1).emit(bus)
    bus.run()
    assert all(e.symbol == "MSFT" for e in events)


def test_ohlcv_constraints() -> None:
    events = _collect_events(n_ticks=20, seed=99)
    for e in events:
        assert e.high >= e.open, "high must be >= open"
        assert e.high >= e.close, "high must be >= close"
        assert e.low <= e.open, "low must be <= open"
        assert e.low <= e.close, "low must be <= close"
        assert e.volume > 0, "volume must be positive"
        assert e.close > 0, "close must be positive"


def test_timestamps_are_strictly_increasing() -> None:
    events = _collect_events(n_ticks=10, seed=7)
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)
    assert len(set(timestamps)) == len(timestamps), "timestamps must be unique"
