"""Tests for ExecutionSimulator."""

from __future__ import annotations

from datetime import datetime

from trading.bus.event_bus import EventBus
from trading.events.types import ApprovedOrderEvent, Direction, FillEvent, OrderType
from trading.execution.simulator import ExecutionSimulator

_REF_PRICE = 200.0


def _make_order(
    direction: Direction = Direction.BUY,
    quantity: int = 100,
    price: float = _REF_PRICE,
) -> ApprovedOrderEvent:
    return ApprovedOrderEvent(
        order_id="test-order-id",
        symbol="AAPL",
        timestamp=datetime(2024, 1, 2, 9, 30),
        order_type=OrderType.MARKET,
        direction=direction,
        quantity=quantity,
        price=price,
    )


def _run(order: ApprovedOrderEvent, seed: int = 0) -> FillEvent:
    bus = EventBus()
    fills: list[FillEvent] = []
    bus.subscribe(FillEvent, fills.append)
    ExecutionSimulator(seed=seed).register(bus)
    bus.publish(order)
    bus.run()
    assert len(fills) == 1
    return fills[0]


def test_fill_created_for_market_order() -> None:
    fill = _run(_make_order())
    assert isinstance(fill, FillEvent)


def test_fill_references_correct_order_id() -> None:
    order = _make_order()
    fill = _run(order)
    assert fill.order_id == order.order_id


def test_fill_direction_matches_order() -> None:
    for direction in (Direction.BUY, Direction.SELL):
        fill = _run(_make_order(direction=direction))
        assert fill.direction is direction


def test_fill_quantity_matches_order() -> None:
    fill = _run(_make_order(quantity=500))
    assert fill.quantity == 500


def test_fill_price_within_slippage_band() -> None:
    sim = ExecutionSimulator(slippage_bps=1, seed=0)
    bus = EventBus()
    fills: list[FillEvent] = []
    bus.subscribe(FillEvent, fills.append)
    sim.register(bus)
    bus.publish(_make_order(price=_REF_PRICE))
    bus.run()

    fill = fills[0]
    max_slip = _REF_PRICE * (1 / 10_000)  # 1 bps
    assert abs(fill.fill_price - _REF_PRICE) <= max_slip + 1e-9


def test_commission_calculation() -> None:
    fill = _run(_make_order(quantity=100))
    assert abs(fill.commission - 1.00) < 1e-6  # $0.01 × 100 = $1.00


def test_fill_id_is_unique() -> None:
    bus = EventBus()
    fills: list[FillEvent] = []
    bus.subscribe(FillEvent, fills.append)
    ExecutionSimulator().register(bus)
    for _ in range(5):
        bus.publish(_make_order())
    bus.run()
    ids = [f.fill_id for f in fills]
    assert len(set(ids)) == len(ids), "fill IDs must be unique"
