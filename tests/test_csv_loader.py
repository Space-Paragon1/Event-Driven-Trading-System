"""Tests for CSVFeed."""

from __future__ import annotations

from pathlib import Path

import pytest

from trading.errors import DataError
from trading.market_data.csv_loader import CSVFeed

HEADER = "date,open,high,low,close,volume\n"
ROWS = (
    "2024-01-02,150.0,151.0,149.0,150.5,1000000\n"
    "2024-01-03,150.5,152.0,150.0,151.0,900000\n"
    "2024-01-04,151.0,153.0,150.5,152.5,1100000\n"
)


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    path = tmp_path / "prices.csv"
    path.write_text(HEADER + ROWS)
    return path


def test_correct_event_count(csv_file: Path) -> None:
    assert len(list(CSVFeed(csv_file, "TEST"))) == 3


def test_symbol_attached(csv_file: Path) -> None:
    assert all(e.symbol == "AAPL" for e in CSVFeed(csv_file, "AAPL"))


def test_ohlcv_values_parsed(csv_file: Path) -> None:
    e = next(iter(CSVFeed(csv_file, "TEST")))
    assert (e.open, e.high, e.low, e.close, e.volume) == (150.0, 151.0, 149.0, 150.5, 1_000_000)


def test_header_is_case_insensitive_and_extra_columns_ignored(tmp_path: Path) -> None:
    path = tmp_path / "p.csv"
    path.write_text("Date,Open,High,Low,Close,Adj Close,Volume\n2024-01-02,1,2,0.5,1.5,1.4,10\n")
    (e,) = CSVFeed(path, "X")
    assert e.close == 1.5


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "p.csv"
    path.write_text(HEADER + ROWS + "\n,,,,,\n")
    assert len(list(CSVFeed(path, "X"))) == 3


def test_alternate_date_format(tmp_path: Path) -> None:
    path = tmp_path / "p.csv"
    path.write_text(HEADER + "01/02/2024,1,1,1,1,1\n")
    (e,) = CSVFeed(path, "X")
    assert e.timestamp.isoformat() == "2024-01-02T00:00:00"


def test_missing_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "p.csv"
    path.write_text("date,open,high,low,close\n2024-01-02,1,1,1,1\n")
    with pytest.raises(DataError, match="volume"):
        list(CSVFeed(path, "X"))


def test_out_of_order_rows_raise(tmp_path: Path) -> None:
    path = tmp_path / "p.csv"
    path.write_text(HEADER + "2024-01-03,1,1,1,1,1\n2024-01-02,1,1,1,1,1\n")
    with pytest.raises(DataError, match="ascending"):
        list(CSVFeed(path, "X"))


def test_bad_value_reports_line_number(tmp_path: Path) -> None:
    path = tmp_path / "p.csv"
    path.write_text(HEADER + "2024-01-02,1,1,1,1,1\n2024-01-03,abc,1,1,1,1\n")
    with pytest.raises(DataError, match=":3:"):
        list(CSVFeed(path, "X"))


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="cannot open"):
        list(CSVFeed(tmp_path / "nope.csv", "X"))
