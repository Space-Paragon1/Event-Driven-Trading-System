"""Tests for CSVFeed."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from trading.bus.event_bus import EventBus
from trading.events.types import MarketDataEvent
from trading.market_data.csv_loader import CSVFeed

_SAMPLE_ROWS = [
    {"date": "2024-01-02", "open": "150.0", "high": "151.0", "low": "149.0", "close": "150.5", "volume": "1000000"},
    {"date": "2024-01-03", "open": "150.5", "high": "152.0", "low": "150.0", "close": "151.0", "volume": "900000"},
    {"date": "2024-01-04", "open": "151.0", "high": "153.0", "low": "150.5", "close": "152.5", "volume": "1100000"},
]


def _write_temp_csv(rows: list[dict]) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    writer = csv.DictWriter(tmp, fieldnames=["date", "open", "high", "low", "close", "volume"])
    writer.writeheader()
    writer.writerows(rows)
    tmp.close()
    return Path(tmp.name)


def _collect(path: Path, symbol: str = "TEST") -> list[MarketDataEvent]:
    bus = EventBus()
    events: list[MarketDataEvent] = []
    bus.subscribe(MarketDataEvent, events.append)
    CSVFeed(path=path, symbol=symbol).emit(bus)
    bus.run()
    return events


def test_correct_event_count() -> None:
    path = _write_temp_csv(_SAMPLE_ROWS)
    events = _collect(path)
    assert len(events) == len(_SAMPLE_ROWS)


def test_symbol_attached() -> None:
    path = _write_temp_csv(_SAMPLE_ROWS)
    events = _collect(path, symbol="AAPL")
    assert all(e.symbol == "AAPL" for e in events)


def test_ohlcv_values_parsed() -> None:
    path = _write_temp_csv(_SAMPLE_ROWS)
    events = _collect(path)
    e = events[0]
    assert e.open == 150.0
    assert e.high == 151.0
    assert e.low == 149.0
    assert e.close == 150.5
    assert e.volume == 1_000_000


def test_timestamps_parsed_in_order() -> None:
    path = _write_temp_csv(_SAMPLE_ROWS)
    events = _collect(path)
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)


def test_ohlcv_constraints() -> None:
    path = _write_temp_csv(_SAMPLE_ROWS)
    events = _collect(path)
    for e in events:
        assert e.high >= e.open
        assert e.high >= e.close
        assert e.low <= e.open
        assert e.low <= e.close
