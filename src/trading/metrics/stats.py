"""Pure performance statistics over equity curves and return series.

All functions take plain sequences, have no side effects, and return
*fractions* (0.05 == 5 %) unless the name says otherwise. Undefined ratios
(e.g. Sharpe of a flat curve) return ``0.0``; unbounded ones (e.g. Calmar
with zero drawdown) return ``math.inf``.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from itertools import pairwise


def simple_returns(equity: Sequence[float]) -> list[float]:
    """Period-over-period simple returns: ``e[i] / e[i-1] - 1``."""
    return [(curr / prev - 1.0) if prev else 0.0 for prev, curr in pairwise(equity)]


def total_return(equity: Sequence[float]) -> float:
    if len(equity) < 2 or not equity[0]:
        return 0.0
    return equity[-1] / equity[0] - 1.0


def cagr(equity: Sequence[float], periods_per_year: float) -> float:
    """Compound annual growth rate, treating each step of *equity* as one period."""
    periods = len(equity) - 1
    if periods <= 0 or equity[0] <= 0 or equity[-1] <= 0:
        return 0.0
    years = periods / periods_per_year
    return float((equity[-1] / equity[0]) ** (1.0 / years) - 1.0)


def annualized_volatility(returns: Sequence[float], periods_per_year: float) -> float:
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns) * math.sqrt(periods_per_year)


def sharpe_ratio(
    returns: Sequence[float], periods_per_year: float, risk_free_rate: float = 0.0
) -> float:
    """Annualised Sharpe ratio (sample standard deviation).

    ``risk_free_rate`` is an annual rate, de-annualised per period.
    """
    if len(returns) < 2:
        return 0.0
    rf = risk_free_rate / periods_per_year
    excess = [r - rf for r in returns]
    std = statistics.stdev(excess)
    if std == 0.0:
        return 0.0
    return statistics.fmean(excess) / std * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: Sequence[float], periods_per_year: float, risk_free_rate: float = 0.0
) -> float:
    """Annualised Sortino ratio: like Sharpe, but penalising only downside deviation."""
    if len(returns) < 2:
        return 0.0
    rf = risk_free_rate / periods_per_year
    excess = [r - rf for r in returns]
    downside = math.sqrt(math.fsum(min(r, 0.0) ** 2 for r in excess) / len(excess))
    mean = statistics.fmean(excess)
    if downside == 0.0:
        return math.inf if mean > 0 else 0.0
    return mean / downside * math.sqrt(periods_per_year)


def drawdown_series(equity: Sequence[float]) -> list[float]:
    """Drawdown from the running peak at each point, as a non-negative fraction."""
    peak = -math.inf
    out: list[float] = []
    for value in equity:
        peak = max(peak, value)
        out.append((peak - value) / peak if peak > 0 else 0.0)
    return out


def max_drawdown(equity: Sequence[float]) -> tuple[float, int]:
    """Deepest peak-to-trough decline and the longest time spent below a peak.

    Returns:
        ``(depth, duration)`` where *depth* is a fraction and *duration* is the
        longest run of consecutive periods with equity below its prior peak.
    """
    depth, longest, current = 0.0, 0, 0
    for dd in drawdown_series(equity):
        depth = max(depth, dd)
        current = current + 1 if dd > 0 else 0
        longest = max(longest, current)
    return depth, longest


def calmar_ratio(cagr_value: float, max_drawdown_value: float) -> float:
    if max_drawdown_value == 0.0:
        return math.inf if cagr_value > 0 else 0.0
    return cagr_value / max_drawdown_value


def profit_factor(pnls: Sequence[float]) -> float:
    """Gross profit divided by gross loss."""
    gross_profit = math.fsum(p for p in pnls if p > 0)
    gross_loss = -math.fsum(p for p in pnls if p < 0)
    if gross_loss == 0.0:
        return math.inf if gross_profit > 0 else 0.0
    return gross_profit / gross_loss
