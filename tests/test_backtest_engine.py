"""End-to-end tests for BacktestEngine: causality, accounting invariants and determinism."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.factories import bar
from trading.backtest.engine import BacktestEngine, BacktestResult
from trading.bus.event_bus import EventBus
from trading.config import BacktestConfig
from trading.errors import DataError
from trading.events.types import (
    Direction,
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    PortfolioUpdateEvent,
)
from trading.signal.base import Signal, Strategy


def _config(**overrides: object) -> BacktestConfig:
    base = {"persistence.enabled": False, "simulation.n_bars": 300, "simulation.seed": 7}
    return BacktestConfig().with_overrides({**base, **overrides})


def _run(**overrides: object) -> BacktestResult:
    return BacktestEngine(_config(**overrides)).run()


class _ListFeed:
    def __init__(self, bars: list[MarketDataEvent]) -> None:
        self.symbol = bars[0].symbol if bars else "AAPL"
        self._bars = bars

    def __iter__(self) -> Iterator[MarketDataEvent]:
        return iter(self._bars)


class _Scripted(Strategy):
    """Emits a fixed direction on given bar indices; HOLD elsewhere."""

    name = "scripted"

    def __init__(self, script: dict[int, Direction]) -> None:
        super().__init__()
        self._script = script
        self._i = -1

    def on_bar(self, bar: MarketDataEvent) -> Signal:
        self._i += 1
        return self._script.get(self._i, Direction.HOLD), 1.0


class _Spy:
    """Records events of interest straight off the bus."""

    def __init__(self) -> None:
        self.bars: list[MarketDataEvent] = []
        self.orders: list[OrderEvent] = []
        self.fills: list[FillEvent] = []
        self.updates: list[PortfolioUpdateEvent] = []

    def register(self, bus: EventBus) -> None:
        bus.subscribe(MarketDataEvent, self.bars.append)
        bus.subscribe(OrderEvent, self.orders.append)
        bus.subscribe(FillEvent, self.fills.append)
        bus.subscribe(PortfolioUpdateEvent, self.updates.append)


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> _Spy:
    """Attach a spy to every bus the engine creates."""
    spy = _Spy()
    original_init = EventBus.__init__

    def init(self: EventBus) -> None:
        original_init(self)
        spy.register(self)

    monkeypatch.setattr(EventBus, "__init__", init)
    return spy


# --------------------------------------------------------------------------- causality


def test_orders_fill_at_next_bar_open_not_final_price(spy: _Spy) -> None:
    """Regression: all bars used to be queued before any signal, so every order was
    priced off the *last* bar of the backtest."""
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 200.0]
    feed = _ListFeed([bar(c, i, open=c - 0.5) for i, c in enumerate(closes)])
    strategy = _Scripted({1: Direction.BUY, 3: Direction.SELL})
    cfg = _config(**{"execution.slippage_bps": 0.0})
    BacktestEngine(cfg, feed=feed, strategy=strategy).run()

    assert [o.price for o in spy.orders] == [101.0, 103.0]  # reference = that bar's close
    assert [(f.direction, f.fill_price) for f in spy.fills] == [
        (Direction.BUY, 101.5),  # bar 2 open
        (Direction.SELL, 103.5),  # bar 4 open
    ]


def test_no_fill_uses_information_from_its_own_signal_bar(spy: _Spy) -> None:
    _run(**{"strategy.type": "random"})
    orders = {o.order_id: o for o in spy.orders}
    assert spy.fills
    for f in spy.fills:
        assert f.timestamp > orders[f.order_id].timestamp


def test_strategy_never_sees_future_bars() -> None:
    seen_at_signal: list[int] = []

    class Peeker(Strategy):
        def __init__(self, feed_bars: list[MarketDataEvent]) -> None:
            super().__init__()
            self.count = 0

        def on_bar(self, bar: MarketDataEvent) -> Signal:
            self.count += 1
            seen_at_signal.append(self.count)
            return Direction.HOLD, 0.0

    bars = [bar(100.0 + i, i) for i in range(10)]
    BacktestEngine(_config(), feed=_ListFeed(bars), strategy=Peeker(bars)).run()
    assert seen_at_signal == list(range(1, 11))


# --------------------------------------------------------------------------- accounting


@pytest.mark.parametrize("strategy", ["ma_crossover", "rsi", "random"])
@pytest.mark.parametrize("allow_short", [False, True])
def test_equity_identity_and_one_snapshot_per_bar(
    spy: _Spy, strategy: str, allow_short: bool
) -> None:
    result = _run(**{"strategy.type": strategy, "order_manager.allow_short": allow_short})
    assert len(spy.updates) == len(spy.bars) == result.report.n_bars
    for update, b in zip(spy.updates, spy.bars, strict=True):
        assert update.timestamp == b.timestamp
        assert update.equity == pytest.approx(update.cash + update.position * b.close, abs=1e-4)


def test_cash_reconciles_with_fills(spy: _Spy) -> None:
    result = _run(**{"strategy.type": "random", "order_manager.allow_short": True})
    cash = result.config.portfolio.starting_cash
    for f in spy.fills:
        cash -= f.signed_quantity * f.fill_price + f.commission
    assert spy.updates[-1].cash == pytest.approx(cash, abs=1e-4)


def test_long_only_never_goes_short(spy: _Spy) -> None:
    _run(**{"strategy.type": "random", "order_manager.allow_short": False})
    assert min(u.position for u in spy.updates) >= 0


def test_position_limit_is_never_breached(spy: _Spy) -> None:
    _run(**{
        "strategy.type": "random",
        "order_manager.allow_short": True,
        "order_manager.quantity": 400,
        "risk.max_position": 300,
    })  # fmt: skip
    assert max(abs(u.position) for u in spy.updates) <= 300


def test_report_matches_result_series() -> None:
    result = _run()
    assert result.report.final_equity == pytest.approx(result.equity_curve[-1][1], abs=0.01)
    assert result.report.total_fills == len(result.fills)
    assert result.report.total_trades == len(result.trades)


# --------------------------------------------------------------------------- determinism & wiring


def test_runs_are_deterministic() -> None:
    a, b = _run(**{"strategy.type": "random"}), _run(**{"strategy.type": "random"})
    assert a.report == b.report
    assert a.fills == b.fills


def test_different_seeds_differ() -> None:
    assert _run(**{"simulation.seed": 1}).prices != _run(**{"simulation.seed": 2}).prices


def test_custom_strategy_can_be_injected() -> None:
    feed = _ListFeed([bar(100.0 + i, i) for i in range(5)])
    result = BacktestEngine(_config(), feed=feed, strategy=_Scripted({0: Direction.BUY})).run()
    assert result.strategy == "scripted"
    assert result.report.total_fills == 1


def test_empty_feed_raises() -> None:
    with pytest.raises(DataError, match="no bars"):
        BacktestEngine(_config(), feed=_ListFeed([])).run()


def test_csv_data_source(tmp_path: Path) -> None:
    path = tmp_path / "p.csv"
    rows = [f"2024-01-{d:02d},{100 + d},{101 + d},{99 + d},{100.5 + d},1000" for d in range(2, 30)]
    path.write_text("date,open,high,low,close,volume\n" + "\n".join(rows) + "\n")
    result = _run(**{"simulation.data_source": "csv", "simulation.csv_path": str(path)})
    assert result.report.n_bars == 28


def test_persistence_writes_one_run(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "runs.db"
    result = _run(**{"persistence.enabled": True, "persistence.db_path": str(db)})
    with sqlite3.connect(db) as conn:
        (run_id,) = conn.execute("SELECT run_id FROM runs").fetchone()
        n_updates = conn.execute("SELECT COUNT(*) FROM portfolio_updates").fetchone()[0]
    assert run_id == result.run_id
    assert n_updates == result.report.n_bars


def test_disabled_persistence_creates_no_file(tmp_path: Path) -> None:
    db = tmp_path / "nope.db"
    _run(**{"persistence.enabled": False, "persistence.db_path": str(db)})
    assert not db.exists()


def test_result_str_and_dict() -> None:
    result = _run()
    assert "AAPL" in str(result)
    assert "PERFORMANCE REPORT" in str(result)
    d = result.to_dict()
    assert d["symbol"] == "AAPL"
    assert d["strategy"] == "ma_crossover"
    assert "sharpe_ratio" in d["metrics"]
