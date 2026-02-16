"""Tests for RiskManager."""

from __future__ import annotations

from datetime import datetime

from trading.bus.event_bus import EventBus
from trading.events.types import (
    ApprovedOrderEvent,
    Direction,
    OrderEvent,
    OrderType,
    PortfolioUpdateEvent,
    RiskVetoEvent,
)
from trading.risk.manager import RiskManager

_TS = datetime(2024, 1, 2, 9, 30)


def _make_order(direction: Direction = Direction.BUY, qty: int = 100) -> OrderEvent:
    return OrderEvent(
        order_id="oid-001",
        symbol="AAPL",
        timestamp=_TS,
        order_type=OrderType.MARKET,
        direction=direction,
        quantity=qty,
        price=150.0,
    )


def _run(order: OrderEvent, risk: RiskManager) -> tuple[list[ApprovedOrderEvent], list[RiskVetoEvent]]:
    bus = EventBus()
    approved: list[ApprovedOrderEvent] = []
    vetoed: list[RiskVetoEvent] = []
    bus.subscribe(ApprovedOrderEvent, approved.append)
    bus.subscribe(RiskVetoEvent, vetoed.append)
    risk.register(bus)
    bus.publish(order)
    bus.run()
    return approved, vetoed


def test_valid_order_is_approved() -> None:
    approved, vetoed = _run(_make_order(qty=100), RiskManager(max_position=500))
    assert len(approved) == 1
    assert len(vetoed) == 0


def test_approved_order_mirrors_original() -> None:
    order = _make_order(qty=50)
    approved, _ = _run(order, RiskManager())
    a = approved[0]
    assert a.order_id == order.order_id
    assert a.direction == order.direction
    assert a.quantity == order.quantity


def test_over_position_is_vetoed() -> None:
    approved, vetoed = _run(_make_order(qty=600), RiskManager(max_position=500))
    assert len(approved) == 0
    assert len(vetoed) == 1
    assert "position limit" in vetoed[0].reason


def test_max_drawdown_veto() -> None:
    risk = RiskManager(max_drawdown_pct=5.0, starting_equity=100_000.0)
    bus = EventBus()
    approved: list[ApprovedOrderEvent] = []
    vetoed: list[RiskVetoEvent] = []
    bus.subscribe(ApprovedOrderEvent, approved.append)
    bus.subscribe(RiskVetoEvent, vetoed.append)
    risk.register(bus)

    # Simulate a big drawdown via a PortfolioUpdateEvent
    bus.publish(
        PortfolioUpdateEvent(
            symbol="AAPL", timestamp=_TS,
            position=0, avg_cost=0.0,
            realized_pnl=0.0, unrealized_pnl=0.0,
            cash=90_000.0, equity=90_000.0,  # 10% drawdown from 100k
        )
    )
    bus.publish(_make_order(qty=100))
    bus.run()

    assert len(approved) == 0
    assert len(vetoed) == 1
    assert "drawdown" in vetoed[0].reason


def test_veto_contains_order_id() -> None:
    order = _make_order(qty=600)
    _, vetoed = _run(order, RiskManager(max_position=500))
    assert vetoed[0].order_id == order.order_id
