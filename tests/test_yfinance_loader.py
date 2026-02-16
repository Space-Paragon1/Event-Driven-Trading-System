"""Tests for YFinanceFeed (mocked — no network calls)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from trading.bus.event_bus import EventBus
from trading.events.types import MarketDataEvent
from trading.market_data.yfinance_loader import YFinanceFeed

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOCK_ROWS = [
    {"Open": 150.0, "High": 151.5, "Low": 149.0, "Close": 150.5, "Volume": 1_000_000},
    {"Open": 150.5, "High": 152.0, "Low": 150.0, "Close": 151.0, "Volume": 900_000},
    {"Open": 151.0, "High": 153.0, "Low": 150.5, "Close": 152.5, "Volume": 1_100_000},
]

_DATES = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])


def _make_mock_df() -> pd.DataFrame:
    df = pd.DataFrame(_MOCK_ROWS, index=_DATES)
    df.index.name = "Date"
    return df


def _collect(symbol: str = "AAPL") -> list[MarketDataEvent]:
    bus = EventBus()
    events: list[MarketDataEvent] = []
    bus.subscribe(MarketDataEvent, events.append)
    feed = YFinanceFeed(symbol=symbol, start="2024-01-01", end="2024-01-05")
    with patch("yfinance.download", return_value=_make_mock_df()):
        feed.emit(bus)
    bus.run()
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_correct_event_count() -> None:
    events = _collect()
    assert len(events) == len(_MOCK_ROWS)


def test_events_are_market_data_events() -> None:
    events = _collect()
    assert all(isinstance(e, MarketDataEvent) for e in events)


def test_ohlcv_values_match_mock() -> None:
    events = _collect()
    e = events[0]
    assert e.open == 150.0
    assert e.high == 151.5
    assert e.low == 149.0
    assert e.close == 150.5
    assert e.volume == 1_000_000


def test_symbol_attached_to_all_events() -> None:
    events = _collect(symbol="TSLA")
    assert all(e.symbol == "TSLA" for e in events)
