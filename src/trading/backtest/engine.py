"""Backtest engine — wires the full pipeline from a config dict and runs it."""

from __future__ import annotations

from dataclasses import dataclass

from trading.bus.event_bus import EventBus
from trading.execution.simulator import ExecutionSimulator
from trading.logger.handler import EventLogger
from trading.market_data.feed import MarketDataFeed
from trading.metrics.calculator import PerformanceMetrics, PerformanceReport
from trading.order_manager.manager import OrderManager
from trading.persistence.sqlite_writer import SQLiteWriter
from trading.portfolio.tracker import PortfolioTracker
from trading.risk.manager import RiskManager
from trading.signal.generator import SignalGenerator
from trading.signal.ma_crossover import MACrossoverStrategy


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
        strategy:
          type: ma_crossover   # or "random"
          fast_period: 5
          slow_period: 20
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

    Args:
        config:     Nested dict (typically loaded from YAML).
        enable_db:  Override ``persistence.enabled``; useful for tests.
    """

    def __init__(self, config: dict, enable_db: bool | None = None) -> None:
        self._config = config
        self._enable_db = enable_db

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

        symbol: str = sim_cfg.get("symbol", "AAPL")
        n_ticks: int = int(sim_cfg.get("n_ticks", 100))
        seed: int | None = sim_cfg.get("seed")
        starting_cash: float = float(port_cfg.get("starting_cash", 100_000.0))

        bus = EventBus()
        feed = MarketDataFeed(symbol=symbol, n_ticks=n_ticks, seed=seed)
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

        for component in [strategy, order_mgr, risk_mgr, exec_sim, portfolio, metrics, event_log]:
            component.register(bus)
        if db:
            db.register(bus)

        feed.emit(bus)
        bus.run()

        if db:
            db.close()

        report = metrics.report()
        return BacktestReport(performance=report, n_ticks=n_ticks, symbol=symbol)

    # ------------------------------------------------------------------

    def _build_strategy(self, strat_cfg: dict, seed: int | None) -> object:
        strategy_type = strat_cfg.get("type", "ma_crossover")
        if strategy_type == "ma_crossover":
            return MACrossoverStrategy(
                fast=int(strat_cfg.get("fast_period", 5)),
                slow=int(strat_cfg.get("slow_period", 20)),
            )
        return SignalGenerator(seed=seed)
