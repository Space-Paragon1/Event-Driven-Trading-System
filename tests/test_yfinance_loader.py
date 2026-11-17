"""Tests for YFinanceFeed (yfinance is mocked; no network access)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("yfinance")

from trading.errors import DataError  # noqa: E402
from trading.market_data.yfinance_loader import YFinanceFeed  # noqa: E402

ROWS = [
    {"Open": 150.0, "High": 151.5, "Low": 149.0, "Close": 150.5, "Volume": 1_000_000},
    {"Open": 150.5, "High": 152.0, "Low": 150.0, "Close": 151.0, "Volume": 900_000},
    {"Open": 151.0, "High": 153.0, "Low": 150.5, "Close": 152.5, "Volume": 1_100_000},
]
DATES = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])


def _collect(df: object, symbol: str = "AAPL") -> list:  # type: ignore[type-arg]
    feed = YFinanceFeed(symbol=symbol, start="2024-01-01", end="2024-01-05")
    with patch("yfinance.download", return_value=df) as download:
        events = list(feed)
    download.assert_called_once()
    return events


def test_one_event_per_row() -> None:
    assert len(_collect(pd.DataFrame(ROWS, index=DATES))) == 3


def test_ohlcv_values_and_symbol() -> None:
    events = _collect(pd.DataFrame(ROWS, index=DATES), symbol="TSLA")
    e = events[0]
    assert (e.open, e.high, e.low, e.close, e.volume) == (150.0, 151.5, 149.0, 150.5, 1_000_000)
    assert all(ev.symbol == "TSLA" for ev in events)


def test_multiindex_columns_are_flattened() -> None:
    df = pd.DataFrame(ROWS, index=DATES)
    df.columns = pd.MultiIndex.from_product([df.columns, ["AAPL"]], names=["Price", "Ticker"])
    assert [e.close for e in _collect(df)] == [150.5, 151.0, 152.5]


def test_timezone_is_stripped() -> None:
    df = pd.DataFrame(ROWS, index=DATES.tz_localize("America/New_York"))
    assert all(e.timestamp.tzinfo is None for e in _collect(df))


def test_rows_with_missing_values_are_dropped() -> None:
    rows = [dict(r) for r in ROWS]
    rows[1]["Close"] = float("nan")
    assert len(_collect(pd.DataFrame(rows, index=DATES))) == 2


def test_empty_download_raises() -> None:
    with pytest.raises(DataError, match="no data"):
        _collect(pd.DataFrame())
