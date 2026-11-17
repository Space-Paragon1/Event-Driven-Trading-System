"""Tests for the pure statistics functions."""

from __future__ import annotations

import math
import statistics

import pytest

from trading.metrics import stats


def test_simple_returns() -> None:
    assert stats.simple_returns([100.0, 110.0, 99.0]) == pytest.approx([0.10, -0.10])
    assert stats.simple_returns([100.0]) == []


def test_total_return() -> None:
    assert stats.total_return([100.0, 150.0, 120.0]) == pytest.approx(0.20)
    assert stats.total_return([100.0]) == 0.0


def test_cagr_of_one_year_equals_total_return() -> None:
    equity = [100.0] + [100.0] * 251 + [125.0]  # 252 periods
    assert stats.cagr(equity, periods_per_year=252) == pytest.approx(0.25)


def test_cagr_compounds_over_multiple_years() -> None:
    equity = [100.0, 121.0]  # one period == half a year at 2 periods/year
    assert stats.cagr(equity, periods_per_year=2) == pytest.approx(1.21**2 - 1)


def test_cagr_degenerate_inputs() -> None:
    assert stats.cagr([100.0], 252) == 0.0
    assert stats.cagr([100.0, 0.0], 252) == 0.0


def test_sharpe_matches_definition() -> None:
    r = [0.01, -0.005, 0.02, 0.0, 0.004]
    expected = statistics.fmean(r) / statistics.stdev(r) * math.sqrt(252)
    assert stats.sharpe_ratio(r, 252) == pytest.approx(expected)


def test_sharpe_uses_per_period_risk_free_rate() -> None:
    r = [0.01, 0.0, 0.02, 0.005]
    rf = 0.0252
    excess = [x - rf / 252 for x in r]
    expected = statistics.fmean(excess) / statistics.stdev(excess) * math.sqrt(252)
    assert stats.sharpe_ratio(r, 252, risk_free_rate=rf) == pytest.approx(expected)


def test_sharpe_undefined_cases_return_zero() -> None:
    assert stats.sharpe_ratio([0.01], 252) == 0.0
    assert stats.sharpe_ratio([0.01, 0.01, 0.01], 252) == 0.0


def test_sortino_ignores_upside_volatility() -> None:
    calm = [0.01, -0.01, 0.01, -0.01]
    wild_upside = [0.05, -0.01, 0.05, -0.01]
    assert stats.sortino_ratio(wild_upside, 252) > stats.sortino_ratio(calm, 252)
    assert stats.sortino_ratio([0.01, 0.02], 252) == math.inf


def test_max_drawdown_depth_and_duration() -> None:
    equity = [100.0, 120.0, 90.0, 110.0, 130.0, 117.0]
    depth, duration = stats.max_drawdown(equity)
    assert depth == pytest.approx(0.25)  # 120 -> 90
    assert duration == 2  # two bars under the 120 peak


def test_drawdown_series_is_zero_at_new_highs() -> None:
    assert stats.drawdown_series([1.0, 2.0, 3.0]) == [0.0, 0.0, 0.0]


def test_calmar_and_profit_factor_edge_cases() -> None:
    assert stats.calmar_ratio(0.2, 0.1) == pytest.approx(2.0)
    assert stats.calmar_ratio(0.2, 0.0) == math.inf
    assert stats.profit_factor([300.0, -100.0, -50.0]) == pytest.approx(2.0)
    assert stats.profit_factor([10.0]) == math.inf
    assert stats.profit_factor([]) == 0.0


def test_annualized_volatility() -> None:
    r = [0.01, -0.02, 0.015, 0.0]
    assert stats.annualized_volatility(r, 52) == pytest.approx(statistics.stdev(r) * math.sqrt(52))
    assert stats.annualized_volatility([0.1], 52) == 0.0
