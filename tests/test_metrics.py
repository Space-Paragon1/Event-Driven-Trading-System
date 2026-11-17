"""Tests for the PerformanceMetrics collector and report."""

from __future__ import annotations

import json
import math

import pytest

from tests.factories import bar, fill, publish_all, snapshot
from trading.bus.event_bus import EventBus
from trading.events.types import Direction
from trading.metrics.calculator import PerformanceMetrics, PerformanceReport

START = 100_000.0


def _report(*events: object, periods_per_year: float = 252) -> PerformanceReport:
    bus = EventBus()
    m = PerformanceMetrics(starting_equity=START, periods_per_year=periods_per_year)
    m.register(bus)
    publish_all(bus, *events)
    return m.report()


def test_return_and_final_equity() -> None:
    r = _report(snapshot(105_000.0, 0), snapshot(110_000.0, 1))
    assert r.total_return_pct == pytest.approx(10.0)
    assert r.final_equity == 110_000.0
    assert r.n_bars == 2


def test_drawdown_is_measured_on_every_bar() -> None:
    """Regression: equity used to be sampled only on fills, hiding intra-trade drawdowns."""
    r = _report(snapshot(110_000.0, 0, position=100), snapshot(88_000.0, 1, position=100),
                snapshot(111_000.0, 2, position=100))  # fmt: skip
    assert r.max_drawdown_pct == pytest.approx(20.0)
    assert r.max_drawdown_bars == 1


def test_win_rate_counts_round_trips_not_fills() -> None:
    """Regression: every fill used to count as a 'trade', and buys could be 'wins'."""
    r = _report(
        fill(Direction.BUY, 100, 10.0, i=0),
        fill(Direction.SELL, 100, 12.0, i=1),  # +200
        fill(Direction.BUY, 100, 12.0, i=2),
        fill(Direction.SELL, 100, 11.0, i=3),  # -100
        fill(Direction.BUY, 100, 11.0, i=4),  # still open
    )
    assert r.total_fills == 5
    assert r.total_trades == 2
    assert r.win_rate_pct == pytest.approx(50.0)
    assert r.profit_factor == pytest.approx(2.0)
    assert r.avg_trade_pnl == pytest.approx(50.0)


def test_benchmark_and_exposure() -> None:
    r = _report(
        bar(100.0, 0), snapshot(START, 0, position=0),
        bar(110.0, 1), snapshot(START, 1, position=100),
        bar(120.0, 2), snapshot(START, 2, position=100),
        bar(125.0, 3), snapshot(START, 3, position=0),
    )  # fmt: skip
    assert r.benchmark_return_pct == pytest.approx(25.0)
    assert r.exposure_pct == pytest.approx(50.0)


def test_annualisation_uses_periods_per_year() -> None:
    events = [snapshot(START * (1 + 0.01 * ((-1) ** i)), i) for i in range(20)]
    daily = _report(*events, periods_per_year=252)
    weekly = _report(*events, periods_per_year=52)
    # Report values are rounded to 4 dp, hence the loose tolerance.
    assert daily.sharpe_ratio / weekly.sharpe_ratio == pytest.approx(math.sqrt(252 / 52), rel=1e-3)


def test_empty_run_reports_zeros() -> None:
    r = _report()
    assert (r.total_trades, r.win_rate_pct, r.sharpe_ratio, r.final_equity) == (0, 0.0, 0.0, START)


def test_to_dict_is_json_safe() -> None:
    r = _report(snapshot(101_000.0, 0), snapshot(102_000.0, 1))  # no drawdown -> Calmar = inf
    assert math.isinf(r.calmar_ratio)
    d = r.to_dict()
    assert d["calmar_ratio"] is None
    json.dumps(d, allow_nan=False)


def test_str_contains_key_metrics() -> None:
    text = str(_report(snapshot(101_000.0, 0)))
    for label in ("PERFORMANCE REPORT", "Total return", "Sharpe ratio", "Max drawdown", "Win rate"):
        assert label in text


def test_invalid_periods_per_year() -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        PerformanceMetrics(periods_per_year=0)
