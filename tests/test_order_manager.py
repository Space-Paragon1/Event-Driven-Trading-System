"""Tests for OrderManager target-position sizing."""

from __future__ import annotations

import pytest

from tests.factories import Capture, bar, fill, publish_all, signal
from trading.bus.event_bus import EventBus
from trading.events.types import Direction, OrderEvent, OrderType, RiskVetoEvent
from trading.order_manager.manager import OrderManager

BUY, SELL, HOLD = Direction.BUY, Direction.SELL, Direction.HOLD


def _setup(**kwargs: object) -> tuple[EventBus, Capture]:
    bus = EventBus()
    OrderManager(**kwargs).register(bus)  # type: ignore[arg-type]
    return bus, Capture(bus, OrderEvent)


def _orders(*events: object, **kwargs: object) -> list[OrderEvent]:
    bus, cap = _setup(**kwargs)
    publish_all(bus, *events)
    return cap[OrderEvent]


def test_buy_from_flat_orders_target_quantity() -> None:
    (o,) = _orders(signal(BUY), quantity=250)
    assert (o.direction, o.quantity, o.order_type) == (BUY, 250, OrderType.MARKET)


def test_hold_creates_no_order() -> None:
    assert _orders(signal(HOLD)) == []


def test_sell_from_flat_long_only_creates_no_order() -> None:
    assert _orders(signal(SELL)) == []


def test_sell_from_flat_with_shorting_opens_short() -> None:
    (o,) = _orders(signal(SELL), quantity=100, allow_short=True)
    assert (o.direction, o.quantity) == (SELL, 100)


def test_repeated_buys_do_not_stack_while_order_is_working() -> None:
    """Regression: fixed-size orders used to pile up exposure on every BUY signal."""
    orders = _orders(signal(BUY, 0), signal(BUY, 1), signal(BUY, 2))
    assert len(orders) == 1


def test_sell_after_fill_exits_long_position() -> None:
    orders = _orders(signal(BUY, 0), fill(BUY, 100, order_id="O000001"), signal(SELL, 1))
    assert [(o.direction, o.quantity) for o in orders] == [(BUY, 100), (SELL, 100)]


def test_reversal_with_shorting_orders_twice_the_size() -> None:
    orders = _orders(
        signal(BUY, 0), fill(BUY, 100, order_id="O000001"), signal(SELL, 1), allow_short=True
    )
    assert [(o.direction, o.quantity) for o in orders] == [(BUY, 100), (SELL, 200)]


def test_vetoed_order_is_dropped_from_projection() -> None:
    bus, cap = _setup()
    publish_all(bus, signal(BUY, 0))
    first = cap[OrderEvent][0]
    veto = RiskVetoEvent(
        symbol="AAPL", timestamp=first.timestamp, order_id=first.order_id, reason="test"
    )
    publish_all(bus, veto, signal(BUY, 1))
    assert len(cap[OrderEvent]) == 2


def test_reference_price_is_latest_close() -> None:
    (o,) = _orders(bar(101.0, 0), bar(105.5, 1), signal(BUY, 1))
    assert o.price == 105.5


def test_order_ids_are_unique_and_sequential() -> None:
    orders = _orders(
        signal(BUY, 0),
        fill(BUY, 100, order_id="O000001"),
        signal(SELL, 1),
        fill(SELL, 100, order_id="O000002"),
        signal(BUY, 2),
    )
    assert [o.order_id for o in orders] == ["O000001", "O000002", "O000003"]


def test_invalid_quantity_raises() -> None:
    with pytest.raises(ValueError, match="quantity"):
        OrderManager(quantity=0)
