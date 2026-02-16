"""Tests for OrderManager."""

from __future__ import annotations

from datetime import datetime

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, OrderEvent, OrderType, SignalEvent
from trading.order_manager.manager import OrderManager


def _publish_signal(bus: EventBus, direction: Direction) -> None:
    bus.publish(
        SignalEvent(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 2, 9, 30),
            direction=direction,
            strength=0.5,
        )
    )


def test_buy_signal_creates_order() -> None:
    bus = EventBus()
    orders: list[OrderEvent] = []
    bus.subscribe(OrderEvent, orders.append)
    OrderManager().register(bus)

    _publish_signal(bus, Direction.BUY)
    bus.run()

    assert len(orders) == 1
    assert orders[0].direction is Direction.BUY


def test_sell_signal_creates_order() -> None:
    bus = EventBus()
    orders: list[OrderEvent] = []
    bus.subscribe(OrderEvent, orders.append)
    OrderManager().register(bus)

    _publish_signal(bus, Direction.SELL)
    bus.run()

    assert len(orders) == 1
    assert orders[0].direction is Direction.SELL


def test_hold_signal_creates_no_order() -> None:
    bus = EventBus()
    orders: list[OrderEvent] = []
    bus.subscribe(OrderEvent, orders.append)
    OrderManager().register(bus)

    _publish_signal(bus, Direction.HOLD)
    bus.run()

    assert orders == []


def test_order_is_market_type() -> None:
    bus = EventBus()
    orders: list[OrderEvent] = []
    bus.subscribe(OrderEvent, orders.append)
    OrderManager().register(bus)

    _publish_signal(bus, Direction.BUY)
    bus.run()

    assert orders[0].order_type is OrderType.MARKET


def test_order_quantity_matches_manager_config() -> None:
    bus = EventBus()
    orders: list[OrderEvent] = []
    bus.subscribe(OrderEvent, orders.append)
    OrderManager(quantity=250).register(bus)

    _publish_signal(bus, Direction.BUY)
    bus.run()

    assert orders[0].quantity == 250


def test_order_id_is_unique_across_signals() -> None:
    bus = EventBus()
    orders: list[OrderEvent] = []
    bus.subscribe(OrderEvent, orders.append)
    OrderManager().register(bus)

    for _ in range(5):
        _publish_signal(bus, Direction.BUY)
    bus.run()

    ids = [o.order_id for o in orders]
    assert len(set(ids)) == len(ids), "order IDs must be unique"
