"""Backtest engine — wires the full pipeline from a config dict and runs it."""

from __future__ import annotations

from dataclasses import dataclass

from trading.bus.event_bus import EventBus
from trading.execution.simulator import ExecutionSimulator
from trading.logger.handler import EventLogger
from trading.market_data.feed import MarketDataFeed
from trading.market_data.yfinance_loader import YFinanceFeed
from trading.metrics.calculator import PerformanceMetrics, PerformanceReport
from trading.order_manager.manager import OrderManager
from trading.persistence.sqlite_writer import SQLiteWriter
from trading.portfolio.tracker import PortfolioTracker
from trading.risk.manager import RiskManager
from trading.signal.generator import SignalGenerator
from trading.signal.ma_crossover import MACrossoverStrategy
from trading.signal.rsi import RSIStrategy
from trading.visualization.chart import EquityChart


@dataclass
class BacktestReport:
    performance: PerformanceReport
    n_ticks: int
    symbol: str

    def __str__(self) -> str:
        return (
            f"\nBacktest: {self.symbol}  ({self.n_ticks} ticks)\n"
            + str(self.performance)
        )


class BacktestEngine:
    """Wires every component from *config* and runs a full simulation.

    Config keys (all optional — defaults shown):

    .. code-block:: yaml

        simulation:
          symbol: AAPL
          n_ticks: 100
          seed: 42
          data_source: synthetic   # or "yfinance"
          start: "2024-01-01"      # yfinance only
          end:   "2024-12-31"      # yfinance only
          interval: "1d"           # yfinance only
        strategy:
          type: ma_crossover   # "ma_crossover", "rsi", or "random"
          fast_period: 5
          slow_period: 20
          period: 14           # rsi
          overbought: 70.0     # rsi
          oversold: 30.0       # rsi
        order_manager:
          quantity: 100
        execution:
          slippage_bps: 1
          commission_per_share: 0.01
        risk:
          max_position: 500
          max_drawdown_pct: 10.0
        portfolio:
          starting_cash: 100000.0
        persistence:
          enabled: true
          db_path: trading.db
        visualization:
          enabled: false
          save_path: equity_curve.png

    Args:
        config:          Nested dict (typically loaded from YAML).
        enable_db:       Override ``persistence.enabled``; useful for tests.
        enable_chart:    Override ``visualization.enabled``; show chart after run.
        chart_save_path: If set, save chart to this path instead of displaying.
    """

    def __init__(
        self,
        config: dict,
        enable_db: bool | None = None,
        enable_chart: bool | None = None,
        chart_save_path: str | None = None,
    ) -> None:
        self._config = config
        self._enable_db = enable_db
        self._enable_chart = enable_chart
        self._chart_save_path = chart_save_path

    # ------------------------------------------------------------------

    def run(self) -> BacktestReport:
        cfg = self._config
        sim_cfg = cfg.get("simulation", {})
        strat_cfg = cfg.get("strategy", {})
        om_cfg = cfg.get("order_manager", {})
        exec_cfg = cfg.get("execution", {})
        risk_cfg = cfg.get("risk", {})
        port_cfg = cfg.get("portfolio", {})
        pers_cfg = cfg.get("persistence", {})
        viz_cfg = cfg.get("visualization", {})

        symbol: str = sim_cfg.get("symbol", "AAPL")
        n_ticks: int = int(sim_cfg.get("n_ticks", 100))
        seed: int | None = sim_cfg.get("seed")
        starting_cash: float = float(port_cfg.get("starting_cash", 100_000.0))

        bus = EventBus()
        feed = self._build_feed(sim_cfg)
        strategy = self._build_strategy(strat_cfg, seed)
        order_mgr = OrderManager(quantity=int(om_cfg.get("quantity", 100)))
        exec_sim = ExecutionSimulator(
            slippage_bps=float(exec_cfg.get("slippage_bps", 1)),
            commission_per_share=float(exec_cfg.get("commission_per_share", 0.01)),
            seed=seed,
        )
        risk_mgr = RiskManager(
            max_position=int(risk_cfg.get("max_position", 500)),
            max_drawdown_pct=float(risk_cfg.get("max_drawdown_pct", 10.0)),
            starting_equity=starting_cash,
        )
        portfolio = PortfolioTracker(starting_cash=starting_cash)
        metrics = PerformanceMetrics(starting_equity=starting_cash)
        event_log = EventLogger()

        db: SQLiteWriter | None = None
        db_enabled = self._enable_db if self._enable_db is not None else pers_cfg.get("enabled", True)
        if db_enabled:
            db = SQLiteWriter(db_path=pers_cfg.get("db_path", "trading.db"))

        chart: EquityChart | None = None
        chart_enabled = (
            self._enable_chart
            if self._enable_chart is not None
            else viz_cfg.get("enabled", False)
        )
        if chart_enabled:
            chart = EquityChart()

        for component in [strategy, order_mgr, risk_mgr, exec_sim, portfolio, metrics, event_log]:
            component.register(bus)
        if db:
            db.register(bus)
        if chart:
            chart.register(bus)

        feed.emit(bus)
        bus.run()

        if db:
            db.close()

        if chart:
            save = self._chart_save_path or viz_cfg.get("save_path") or None
            chart.plot(symbol=symbol, save_path=save)

        report = metrics.report()
        return BacktestReport(performance=report, n_ticks=n_ticks, symbol=symbol)

    # ------------------------------------------------------------------

    def _build_feed(self, sim_cfg: dict) -> object:
        source = sim_cfg.get("data_source", "synthetic")
        symbol = sim_cfg.get("symbol", "AAPL")
        if source == "yfinance":
            return YFinanceFeed(
                symbol=symbol,
                start=sim_cfg.get("start", "2024-01-01"),
                end=sim_cfg.get("end", "2024-12-31"),
                interval=sim_cfg.get("interval", "1d"),
            )
        return MarketDataFeed(
            symbol=symbol,
            n_ticks=int(sim_cfg.get("n_ticks", 100)),
            seed=sim_cfg.get("seed"),
        )

    def _build_strategy(self, strat_cfg: dict, seed: int | None) -> object:
        strategy_type = strat_cfg.get("type", "ma_crossover")
        if strategy_type == "ma_crossover":
            return MACrossoverStrategy(
                fast=int(strat_cfg.get("fast_period", 5)),
                slow=int(strat_cfg.get("slow_period", 20)),
            )
        if strategy_type == "rsi":
            return RSIStrategy(
                period=int(strat_cfg.get("period", 14)),
                overbought=float(strat_cfg.get("overbought", 70.0)),
                oversold=float(strat_cfg.get("oversold", 30.0)),
            )
        return SignalGenerator(seed=seed)
