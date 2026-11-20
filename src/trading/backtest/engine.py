"""Backtest engine — wires the pipeline from a config and drives it bar by bar."""

from __future__ import annotations

import contextlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from trading.bus.event_bus import Component, EventBus
from trading.config import BacktestConfig
from trading.errors import DataError
from trading.events.types import EndOfBarEvent, FillEvent
from trading.execution.simulator import ExecutionSimulator
from trading.logger.handler import EventLogger
from trading.market_data.csv_loader import CSVFeed
from trading.market_data.feed import Feed, SyntheticFeed
from trading.market_data.yfinance_loader import YFinanceFeed
from trading.metrics.calculator import PerformanceMetrics, PerformanceReport
from trading.metrics.trades import Trade
from trading.order_manager.manager import OrderManager
from trading.persistence.sqlite_writer import SQLiteWriter
from trading.portfolio.tracker import PortfolioTracker
from trading.risk.manager import RiskManager
from trading.signal.base import Strategy
from trading.signal.registry import build_strategy

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestResult:
    """Everything a run produced: the report plus the series needed to analyse or plot it."""

    run_id: str
    config: BacktestConfig
    strategy: str
    report: PerformanceReport
    equity_curve: tuple[tuple[datetime, float], ...]
    prices: tuple[tuple[datetime, float], ...]
    fills: tuple[FillEvent, ...]
    trades: tuple[Trade, ...]

    @property
    def symbol(self) -> str:
        return self.config.simulation.symbol

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "data_source": self.config.simulation.data_source,
            "metrics": self.report.to_dict(),
        }

    def __str__(self) -> str:
        sim = self.config.simulation
        first = self.prices[0][0].date() if self.prices else "-"
        last = self.prices[-1][0].date() if self.prices else "-"
        header = (
            f"\nBacktest  {self.symbol} | {self.strategy} | {sim.data_source} data | "
            f"{self.report.n_bars} bars ({first} to {last})"
        )
        return header + "\n" + str(self.report)


class BacktestEngine:
    """Builds every component from a :class:`BacktestConfig` and runs the simulation.

    **The event loop.** For each bar the engine:

    1. publishes the :class:`MarketDataEvent` and drains the bus, which lets
       the whole cascade (fills for orders from the previous bar, the new
       signal, the order, the risk decision) settle, and then
    2. publishes an :class:`EndOfBarEvent` and drains again, which triggers the
       portfolio's mark-to-market snapshot.

    Only then is the next bar read. Every component therefore sees a strictly
    causal stream, and orders placed on bar *t* fill on bar *t+1*.

    Args:
        config:   Run configuration.
        feed:     Optional feed override (defaults to the one in *config*).
        strategy: Optional strategy override, e.g. a custom :class:`Strategy`
                  subclass that is not in the registry.
    """

    def __init__(
        self,
        config: BacktestConfig | None = None,
        *,
        feed: Feed | None = None,
        strategy: Strategy | None = None,
    ) -> None:
        self.config = config or BacktestConfig()
        self._feed = feed
        self._strategy = strategy

    def run(self) -> BacktestResult:
        cfg = self.config
        run_id = uuid.uuid4().hex[:12]
        cash = cfg.portfolio.starting_cash

        feed = self._feed if self._feed is not None else build_feed(cfg)
        strategy = (
            self._strategy
            if self._strategy is not None
            else build_strategy(cfg.strategy, cfg.simulation.seed)
        )
        strategy_name = strategy.name
        execution = ExecutionSimulator(
            slippage_bps=cfg.execution.slippage_bps,
            commission_per_share=cfg.execution.commission_per_share,
        )
        metrics = PerformanceMetrics(
            starting_equity=cash,
            periods_per_year=cfg.periods_per_year,
            risk_free_rate=cfg.metrics.risk_free_rate,
        )

        bus = EventBus()
        components: list[Component] = [
            execution,
            PortfolioTracker(starting_cash=cash),
            strategy,
            OrderManager(cfg.order_manager.quantity, cfg.order_manager.allow_short),
            RiskManager(cfg.risk.max_position, cfg.risk.max_drawdown_pct, starting_equity=cash),
            metrics,
            EventLogger(),
        ]

        with contextlib.ExitStack() as stack:
            db: SQLiteWriter | None = None
            if cfg.persistence.enabled:
                db = stack.enter_context(SQLiteWriter(cfg.persistence.db_path, run_id))
                db.start_run(symbol=feed.symbol, strategy=strategy_name, config=cfg.to_dict())
                components.append(db)

            for component in components:
                component.register(bus)

            for bar in feed:
                bus.publish(bar)
                bus.run()
                bus.publish(EndOfBarEvent(symbol=bar.symbol, timestamp=bar.timestamp))
                bus.run()

            if not metrics.equity_curve:
                raise DataError(f"the {cfg.simulation.data_source} feed produced no bars")
            if execution.working_orders:
                log.info(
                    "%d order(s) still working when the data ended (never filled)",
                    execution.working_orders,
                )

            report = metrics.report()
            if db is not None:
                db.finish_run(report.to_dict())

        return BacktestResult(
            run_id=run_id,
            config=cfg,
            strategy=strategy_name,
            report=report,
            equity_curve=tuple(metrics.equity_curve),
            prices=tuple(metrics.prices),
            fills=tuple(metrics.fills),
            trades=tuple(metrics.trades),
        )


def build_feed(cfg: BacktestConfig) -> Feed:
    """Construct the feed described by ``cfg.simulation``."""
    sim = cfg.simulation
    if sim.data_source == "yfinance":
        return YFinanceFeed(sim.symbol, start=sim.start, end=sim.end, interval=sim.interval)
    if sim.data_source == "csv":
        assert sim.csv_path is not None  # guaranteed by SimulationConfig validation
        return CSVFeed(sim.csv_path, symbol=sim.symbol)
    return SyntheticFeed(
        sim.symbol,
        n_bars=sim.n_bars,
        seed=sim.seed,
        start_price=sim.start_price,
        annual_drift=sim.annual_drift,
        annual_volatility=sim.annual_volatility,
    )
