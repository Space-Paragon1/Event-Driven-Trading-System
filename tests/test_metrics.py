"""Tests for PerformanceMetrics."""

from __future__ import annotations

from datetime import datetime

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, FillEvent, PortfolioUpdateEvent
from trading.metrics.calculator import PerformanceMetrics

_TS = datetime(2024, 1, 2, 9, 30)
_START = 100_000.0


def _make_portfolio_event(equity: float, symbol: str = "AAPL",
                          avg_cost: float = 150.0, position: int = 0) -> PortfolioUpdateEvent:
    return PortfolioUpdateEvent(
        symbol=symbol, timestamp=_TS,
        position=position, avg_cost=avg_cost,
        realized_pnl=0.0, unrealized_pnl=0.0,
        cash=equity, equity=equity,
    )


def _make_fill(direction: Direction = Direction.BUY,
               price: float = 150.0, qty: int = 100) -> FillEvent:
    return FillEvent(
        fill_id="fid", order_id="oid", symbol="AAPL", timestamp=_TS,
        direction=direction, quantity=qty, fill_price=price, commission=0.0,
    )


def _run(events: list) -> PerformanceMetrics:
    bus = EventBus()
    m = PerformanceMetrics(starting_equity=_START)
    m.register(bus)
    for e in events:
        bus.publish(e)
    bus.run()
    return m


def test_positive_return() -> None:
    m = _run([_make_portfolio_event(equity=110_000.0)])
    r = m.report()
    assert r.total_return_pct > 0


def test_negative_return() -> None:
    m = _run([_make_portfolio_event(equity=90_000.0)])
    r = m.report()
    assert r.total_return_pct < 0


def test_max_drawdown_detected() -> None:
    events = [
        _make_portfolio_event(110_000.0),   # new peak
        _make_portfolio_event(99_000.0),    # drawdown from 110k
    ]
    m = _run(events)
    r = m.report()
    expected_dd = (110_000 - 99_000) / 110_000 * 100
    assert abs(r.max_drawdown_pct - expected_dd) < 1e-3


def test_win_rate_all_profitable() -> None:
    # fills with price > avg_cost → profitable buys
    m = PerformanceMetrics(starting_equity=_START)
    bus = EventBus()
    m.register(bus)
    # first set avg_cost via a portfolio event
    bus.publish(_make_portfolio_event(equity=_START, avg_cost=100.0, position=100))
    # fill at price above avg_cost
    bus.publish(_make_fill(direction=Direction.BUY, price=120.0))
    bus.run()
    r = m.report()
    assert r.win_rate == 1.0


def test_report_fields_present() -> None:
    m = _run([_make_portfolio_event(105_000.0)])
    r = m.report()
    assert hasattr(r, "total_return_pct")
    assert hasattr(r, "max_drawdown_pct")
    assert hasattr(r, "sharpe_ratio")
    assert hasattr(r, "win_rate")
    assert hasattr(r, "total_trades")
    assert hasattr(r, "final_equity")


def test_zero_trades_win_rate() -> None:
    m = _run([])
    assert m.report().win_rate == 0.0
    assert m.report().total_trades == 0
