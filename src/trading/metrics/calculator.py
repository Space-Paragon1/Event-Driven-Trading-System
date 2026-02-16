"""Performance metrics calculator."""

from __future__ import annotations

import math
from dataclasses import dataclass

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, FillEvent, PortfolioUpdateEvent


@dataclass
class PerformanceReport:
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float       # annualised, assuming 252 trading days
    win_rate: float           # fraction of trades that were profitable
    total_trades: int
    profitable_trades: int
    final_equity: float

    def __str__(self) -> str:
        lines = [
            "",
            "=" * 44,
            "  PERFORMANCE REPORT",
            "=" * 44,
            f"  Total return      : {self.total_return_pct:+.2f} %",
            f"  Max drawdown      : {self.max_drawdown_pct:.2f} %",
            f"  Sharpe ratio      : {self.sharpe_ratio:.4f}",
            f"  Win rate          : {self.win_rate * 100:.1f} %",
            f"  Total trades      : {self.total_trades}",
            f"  Profitable trades : {self.profitable_trades}",
            f"  Final equity      : ${self.final_equity:,.2f}",
            "=" * 44,
            "",
        ]
        return "\n".join(lines)


class PerformanceMetrics:
    """Tracks equity snapshots and trade outcomes to produce a
    :class:`PerformanceReport` at the end of a simulation.

    Subscribe to the bus via :meth:`register`, then call :meth:`report`
    after :meth:`~trading.bus.event_bus.EventBus.run` completes.

    Args:
        starting_equity: Starting portfolio value used for return calculation.
    """

    def __init__(self, starting_equity: float = 100_000.0) -> None:
        self._starting_equity = starting_equity
        self._equity_curve: list[float] = [starting_equity]
        self._peak_equity: float = starting_equity
        self._max_drawdown_pct: float = 0.0
        # trade log: list of (cost_basis, fill_price, direction, qty)
        self._trades: list[tuple[float, float, Direction, int]] = []
        self._last_avg_cost: dict[str, float] = {}

    def register(self, bus: EventBus) -> None:
        bus.subscribe(PortfolioUpdateEvent, self._on_portfolio_update)
        bus.subscribe(FillEvent, self._on_fill)

    # ------------------------------------------------------------------

    def _on_portfolio_update(self, event: PortfolioUpdateEvent) -> None:
        eq = event.equity
        self._equity_curve.append(eq)
        if eq > self._peak_equity:
            self._peak_equity = eq
        elif self._peak_equity > 0:
            dd = (self._peak_equity - eq) / self._peak_equity * 100
            if dd > self._max_drawdown_pct:
                self._max_drawdown_pct = dd
        # keep avg_cost for win/loss determination
        self._last_avg_cost[event.symbol] = event.avg_cost

    def _on_fill(self, event: FillEvent) -> None:
        avg_cost = self._last_avg_cost.get(event.symbol, event.fill_price)
        self._trades.append((avg_cost, event.fill_price, event.direction, event.quantity))

    # ------------------------------------------------------------------

    def report(self) -> PerformanceReport:
        final_equity = self._equity_curve[-1] if self._equity_curve else self._starting_equity
        total_return = (final_equity - self._starting_equity) / self._starting_equity * 100

        sharpe = self._sharpe()

        profitable = sum(
            1
            for cost, price, direction, _ in self._trades
            if (direction is Direction.BUY and price > cost)
            or (direction is Direction.SELL and price < cost)
        )
        total = len(self._trades)
        win_rate = profitable / total if total else 0.0

        return PerformanceReport(
            total_return_pct=round(total_return, 4),
            max_drawdown_pct=round(self._max_drawdown_pct, 4),
            sharpe_ratio=round(sharpe, 4),
            win_rate=round(win_rate, 4),
            total_trades=total,
            profitable_trades=profitable,
            final_equity=round(final_equity, 2),
        )

    def _sharpe(self) -> float:
        """Annualised Sharpe ratio from equity curve (risk-free rate = 0)."""
        curve = self._equity_curve
        if len(curve) < 2:
            return 0.0
        returns = [(curve[i] - curve[i - 1]) / curve[i - 1] for i in range(1, len(curve))]
        n = len(returns)
        mean = sum(returns) / n
        variance = sum((r - mean) ** 2 for r in returns) / n
        std = math.sqrt(variance)
        if std == 0.0:
            return 0.0
        return mean / std * math.sqrt(252)
