"""Tests for incremental indicators."""

from __future__ import annotations

import pytest

from trading.signal.indicators import RSI, SMA


def test_sma_warmup_then_values() -> None:
    sma = SMA(3)
    assert [sma.update(x) for x in [1.0, 2.0, 3.0, 4.0, 5.0]] == [None, None, 2.0, 3.0, 4.0]


def test_sma_rejects_bad_period() -> None:
    with pytest.raises(ValueError, match="period"):
        SMA(0)


# Wilder's worked example (14-period RSI), as reproduced in StockCharts' ChartSchool.
WILDER_PRICES = [
    44.3389, 44.0902, 44.1497, 43.6124, 44.3278, 44.8264, 45.0955, 45.4245, 45.8433, 46.0826,
    45.8931, 46.0328, 45.6140, 46.2820, 46.2820, 46.0028, 46.0328, 46.4116, 46.2222, 45.6439,
]  # fmt: skip
WILDER_RSI = [70.53, 66.32, 66.55, 69.41, 66.36, 57.97]


def test_rsi_matches_wilder_reference() -> None:
    rsi = RSI(14)
    values = [rsi.update(p) for p in WILDER_PRICES]
    assert values[:14] == [None] * 14
    assert values[14:] == pytest.approx(WILDER_RSI, abs=0.01)


def test_rsi_extremes_and_flat() -> None:
    up, down, flat = RSI(3), RSI(3), RSI(3)
    for i in range(6):
        u, d, f = up.update(100.0 + i), down.update(100.0 - i), flat.update(100.0)
    assert (u, d, f) == (100.0, 0.0, 50.0)


def test_rsi_bounded() -> None:
    rsi = RSI(5)
    prices = [100, 103, 99, 104, 98, 105, 97, 106, 96, 107, 95.0]
    for p in prices:
        value = rsi.update(p)
        assert value is None or 0.0 <= value <= 100.0


def test_rsi_rejects_bad_period() -> None:
    with pytest.raises(ValueError, match="period"):
        RSI(1)
