"""Tests for PortfolioTracker."""

from __future__ import annotations

from datetime import datetime

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, FillEvent, MarketDataEvent, PortfolioUpdateEvent
from trading.portfolio.tracker import PortfolioTracker

_TS = datetime(2024, 1, 2, 9, 30)
_STARTING_CASH = 100_000.0


def _make_fill(direction: Direction, qty: int = 100, price: float = 150.0,
               commission: float = 1.0) -> FillEvent:
    return FillEvent(
        fill_id="fid-001",
        order_id="oid-001",
        symbol="AAPL",
        timestamp=_TS,
        direction=direction,
        quantity=qty,
        fill_price=price,
        commission=commission,
    )


def _make_market_data(close: float) -> MarketDataEvent:
    return MarketDataEvent(
        symbol="AAPL", timestamp=_TS,
        open=close, high=close, low=close, close=close, volume=1000,
    )


def _run_fills(fills: list[FillEvent],
               market_data: list[MarketDataEvent] | None = None,
               starting_cash: float = _STARTING_CASH) -> list[PortfolioUpdateEvent]:
    bus = EventBus()
    updates: list[PortfolioUpdateEvent] = []
    bus.subscribe(PortfolioUpdateEvent, updates.append)
    PortfolioTracker(starting_cash=starting_cash).register(bus)
    for md in (market_data or []):
        bus.publish(md)
    for f in fills:
        bus.publish(f)
    bus.run()
    return updates


def test_buy_debits_cash() -> None:
    updates = _run_fills([_make_fill(Direction.BUY, qty=100, price=150.0, commission=1.0)])
    assert len(updates) == 1
    u = updates[0]
    expected_cash = _STARTING_CASH - 100 * 150.0 - 1.0
    assert abs(u.cash - expected_cash) < 1e-4


def test_sell_credits_cash() -> None:
    # buy first then sell
    updates = _run_fills([
        _make_fill(Direction.BUY, qty=100, price=150.0, commission=1.0),
        _make_fill(Direction.SELL, qty=100, price=155.0, commission=1.0),
    ])
    assert len(updates) == 2
    final = updates[-1]
    # cash after sell: (100k - 100*150 - 1) + (100*155 - 1) = 100k + 500 - 2
    expected_cash = _STARTING_CASH + (155.0 - 150.0) * 100 - 2.0
    assert abs(final.cash - expected_cash) < 1e-4


def test_realized_pnl_on_sell() -> None:
    updates = _run_fills([
        _make_fill(Direction.BUY, qty=100, price=150.0, commission=0.0),
        _make_fill(Direction.SELL, qty=100, price=160.0, commission=0.0),
    ])
    final = updates[-1]
    assert abs(final.realized_pnl - 1000.0) < 1e-4  # (160-150)*100


def test_position_zero_after_round_trip() -> None:
    updates = _run_fills([
        _make_fill(Direction.BUY, qty=100, price=150.0),
        _make_fill(Direction.SELL, qty=100, price=155.0),
    ])
    assert updates[-1].position == 0


def test_update_published_per_fill() -> None:
    fills = [_make_fill(Direction.BUY) for _ in range(3)]
    updates = _run_fills(fills)
    assert len(updates) == 3


def test_equity_includes_market_value() -> None:
    md = _make_market_data(close=160.0)
    updates = _run_fills(
        [_make_fill(Direction.BUY, qty=100, price=150.0, commission=0.0)],
        market_data=[md],
    )
    u = updates[0]
    # equity = cash + position * last_price
    expected = (_STARTING_CASH - 100 * 150.0) + 100 * 160.0
    assert abs(u.equity - expected) < 1e-4
