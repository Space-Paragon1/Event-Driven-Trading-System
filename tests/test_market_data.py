"""Tests for SyntheticFeed."""

from __future__ import annotations

import pytest

from trading.market_data.feed import SyntheticFeed


def test_emits_requested_number_of_bars() -> None:
    assert len(list(SyntheticFeed("TEST", n_bars=37, seed=0))) == 37


def test_symbol_attached() -> None:
    assert all(b.symbol == "MSFT" for b in SyntheticFeed("MSFT", n_bars=5, seed=1))


def test_deterministic_for_seed() -> None:
    assert list(SyntheticFeed("X", n_bars=50, seed=7)) == list(
        SyntheticFeed("X", n_bars=50, seed=7)
    )
    assert list(SyntheticFeed("X", n_bars=50, seed=7)) != list(
        SyntheticFeed("X", n_bars=50, seed=8)
    )


def test_iterating_twice_replays_the_same_bars() -> None:
    feed = SyntheticFeed("X", n_bars=20, seed=3)
    assert list(feed) == list(feed)


def test_ohlcv_constraints() -> None:
    for b in SyntheticFeed("TEST", n_bars=500, seed=99, annual_volatility=0.8):
        assert b.low <= min(b.open, b.close) <= max(b.open, b.close) <= b.high
        assert b.low > 0
        assert b.volume > 0


def test_timestamps_are_increasing_weekdays() -> None:
    stamps = [b.timestamp for b in SyntheticFeed("TEST", n_bars=30, seed=7)]
    assert stamps == sorted(set(stamps))
    assert all(t.weekday() < 5 for t in stamps)


def test_zero_volatility_follows_drift_deterministically() -> None:
    closes = [b.close for b in SyntheticFeed("X", n_bars=10, seed=1, annual_volatility=0.0)]
    assert closes == sorted(closes)  # positive drift, no noise


@pytest.mark.parametrize(
    "kwargs", [{"n_bars": -1}, {"start_price": 0.0}, {"annual_volatility": -0.1}]
)
def test_invalid_parameters_raise(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        SyntheticFeed("X", **kwargs)  # type: ignore[arg-type]
