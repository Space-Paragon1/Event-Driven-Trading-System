"""Performance metrics: collects the per-bar equity curve and fills, then computes a report."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime

from trading.bus.event_bus import EventBus
from trading.events.types import FillEvent, MarketDataEvent, PortfolioUpdateEvent
from trading.metrics import stats
from trading.metrics.trades import Trade, TradeTracker


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    """Summary statistics for one backtest. ``*_pct`` fields are percentages."""

    starting_equity: float
    final_equity: float
    n_bars: int
    total_return_pct: float
    cagr_pct: float
    annual_volatility_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    max_drawdown_bars: int
    calmar_ratio: float
    benchmark_return_pct: float  # buy-and-hold, first close to last close
    total_trades: int  # closed round trips
    win_rate_pct: float
    profit_factor: float
    avg_trade_pnl: float
    total_fills: int
    total_commission: float
    exposure_pct: float  # share of bars with a non-zero position

    def to_dict(self) -> dict[str, float | int | None]:
        """JSON-safe dict (non-finite values become ``None``)."""
        return {k: _finite_or_none(v) for k, v in asdict(self).items()}

    def __str__(self) -> str:
        rows = [
            ("Final equity", f"${self.final_equity:,.2f}"),
            ("Total return", f"{self.total_return_pct:+.2f} %"),
            ("Buy & hold", f"{self.benchmark_return_pct:+.2f} %"),
            ("CAGR", f"{self.cagr_pct:+.2f} %"),
            ("Volatility (ann.)", f"{self.annual_volatility_pct:.2f} %"),
            ("Sharpe ratio", _fmt_ratio(self.sharpe_ratio)),
            ("Sortino ratio", _fmt_ratio(self.sortino_ratio)),
            ("Max drawdown", f"{self.max_drawdown_pct:.2f} %  ({self.max_drawdown_bars} bars)"),
            ("Calmar ratio", _fmt_ratio(self.calmar_ratio)),
            None,
            ("Round trips", f"{self.total_trades}"),
            ("Win rate", f"{self.win_rate_pct:.1f} %"),
            ("Profit factor", _fmt_ratio(self.profit_factor)),
            ("Avg trade P&L", f"${self.avg_trade_pnl:,.2f}"),
            ("Fills", f"{self.total_fills}"),
            ("Commission", f"${self.total_commission:,.2f}"),
            ("Exposure", f"{self.exposure_pct:.1f} %"),
        ]
        width = 46
        lines = ["", "=" * width, "  PERFORMANCE REPORT", "=" * width]
        for row in rows:
            lines.append("-" * width if row is None else f"  {row[0]:<20}{row[1]:>24}")
        lines += ["=" * width, ""]
        return "\n".join(lines)


class PerformanceMetrics:
    """Event-driven metrics collector.

    Records one equity point per :class:`PortfolioUpdateEvent` (one per bar),
    every fill, and every close price, then computes a
    :class:`PerformanceReport` on demand.

    Args:
        starting_equity:  Equity before the first bar.
        periods_per_year: Bars per year, used to annualise returns
            (252 for daily bars, 52 weekly, 252 × 390 for 1-minute bars).
        risk_free_rate:   Annual risk-free rate for Sharpe/Sortino.
    """

    def __init__(
        self,
        starting_equity: float = 100_000.0,
        periods_per_year: float = 252,
        risk_free_rate: float = 0.0,
    ) -> None:
        if periods_per_year <= 0:
            raise ValueError(f"periods_per_year must be positive, got {periods_per_year}")
        self.starting_equity = starting_equity
        self.periods_per_year = periods_per_year
        self.risk_free_rate = risk_free_rate
        self.equity_curve: list[tuple[datetime, float]] = []
        self.prices: list[tuple[datetime, float]] = []
        self.fills: list[FillEvent] = []
        self._trades = TradeTracker()
        self._bars_exposed = 0

    def register(self, bus: EventBus) -> None:
        bus.subscribe(MarketDataEvent, self._on_market_data)
        bus.subscribe(FillEvent, self._on_fill)
        bus.subscribe(PortfolioUpdateEvent, self._on_portfolio_update)

    @property
    def trades(self) -> list[Trade]:
        return self._trades.trades

    # ------------------------------------------------------------------

    def _on_market_data(self, event: MarketDataEvent) -> None:
        self.prices.append((event.timestamp, event.close))

    def _on_fill(self, event: FillEvent) -> None:
        self.fills.append(event)
        self._trades.on_fill(event)

    def _on_portfolio_update(self, event: PortfolioUpdateEvent) -> None:
        self.equity_curve.append((event.timestamp, event.equity))
        if event.position != 0:
            self._bars_exposed += 1

    # ------------------------------------------------------------------

    def report(self) -> PerformanceReport:
        equity = [self.starting_equity, *(e for _, e in self.equity_curve)]
        returns = stats.simple_returns(equity)
        ppy = self.periods_per_year
        dd_depth, dd_bars = stats.max_drawdown(equity)
        cagr = stats.cagr(equity, ppy)
        pnls = [t.pnl for t in self.trades]
        wins = sum(1 for p in pnls if p > 0)
        n_bars = len(self.equity_curve)
        closes = [c for _, c in self.prices]

        return PerformanceReport(
            starting_equity=round(self.starting_equity, 2),
            final_equity=round(equity[-1], 2),
            n_bars=n_bars,
            total_return_pct=round(stats.total_return(equity) * 100, 4),
            cagr_pct=round(cagr * 100, 4),
            annual_volatility_pct=round(stats.annualized_volatility(returns, ppy) * 100, 4),
            sharpe_ratio=round(stats.sharpe_ratio(returns, ppy, self.risk_free_rate), 4),
            sortino_ratio=round(stats.sortino_ratio(returns, ppy, self.risk_free_rate), 4),
            max_drawdown_pct=round(dd_depth * 100, 4),
            max_drawdown_bars=dd_bars,
            calmar_ratio=round(stats.calmar_ratio(cagr, dd_depth), 4),
            benchmark_return_pct=round(stats.total_return(closes) * 100, 4),
            total_trades=len(pnls),
            win_rate_pct=round(wins / len(pnls) * 100, 4) if pnls else 0.0,
            profit_factor=round(stats.profit_factor(pnls), 4),
            avg_trade_pnl=round(math.fsum(pnls) / len(pnls), 2) if pnls else 0.0,
            total_fills=len(self.fills),
            total_commission=round(math.fsum(f.commission for f in self.fills), 2),
            exposure_pct=round(self._bars_exposed / n_bars * 100, 4) if n_bars else 0.0,
        )


def _finite_or_none(value: float | int) -> float | int | None:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _fmt_ratio(value: float) -> str:
    return "inf" if math.isinf(value) else f"{value:.3f}"
