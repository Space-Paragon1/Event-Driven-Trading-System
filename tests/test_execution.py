"""Tests for ExecutionSimulator."""

from __future__ import annotations

import pytest

from tests.factories import Capture, approved, bar, publish_all
from trading.bus.event_bus import EventBus
from trading.events.types import Direction, FillEvent, OrderType
from trading.execution.simulator import ExecutionSimulator

BUY, SELL = Direction.BUY, Direction.SELL


def _setup(**kwargs: float) -> tuple[EventBus, ExecutionSimulator, Capture]:
    bus = EventBus()
    sim = ExecutionSimulator(**kwargs)
    sim.register(bus)
    return bus, sim, Capture(bus, FillEvent)


def test_order_is_not_filled_until_next_bar() -> None:
    bus, sim, cap = _setup()
    publish_all(bus, bar(100.0, 0), approved(BUY, i=0))
    assert cap[FillEvent] == []
    assert sim.working_orders == 1

    publish_all(bus, bar(102.0, 1, open=101.0))
    (f,) = cap[FillEvent]
    assert f.timestamp == bar(0.0, 1).timestamp
    assert sim.working_orders == 0


def test_fills_at_next_open_with_adverse_slippage() -> None:
    bus, _, cap = _setup(slippage_bps=10, commission_per_share=0.0)
    publish_all(
        bus,
        approved(BUY, order_id="B"),
        approved(SELL, order_id="S"),
        bar(close=250.0, i=1, open=200.0),
    )
    by_id = {f.order_id: f for f in cap[FillEvent]}
    assert by_id["B"].fill_price == pytest.approx(200.0 * 1.001)
    assert by_id["S"].fill_price == pytest.approx(200.0 * 0.999)


def test_zero_slippage_fills_exactly_at_open() -> None:
    bus, _, cap = _setup(slippage_bps=0)
    publish_all(bus, approved(BUY), bar(close=99.0, i=1, open=98.76))
    assert cap[FillEvent][0].fill_price == 98.76


def test_fill_mirrors_order() -> None:
    bus, _, cap = _setup()
    o = approved(SELL, 500, order_id="X42")
    publish_all(bus, o, bar(100.0, 1))
    f = cap[FillEvent][0]
    assert (f.order_id, f.direction, f.quantity, f.symbol) == ("X42", SELL, 500, "AAPL")


def test_commission_per_share() -> None:
    bus, _, cap = _setup(commission_per_share=0.005)
    publish_all(bus, approved(BUY, 300), bar(100.0, 1))
    assert cap[FillEvent][0].commission == pytest.approx(1.5)


def test_bars_for_other_symbols_do_not_fill() -> None:
    bus, sim, cap = _setup()
    publish_all(bus, approved(BUY, symbol="AAPL"), bar(100.0, 1, symbol="MSFT"))
    assert cap[FillEvent] == []
    assert sim.working_orders == 1


def test_fill_ids_are_unique() -> None:
    bus, _, cap = _setup()
    publish_all(bus, *[approved(BUY, order_id=f"O{i}") for i in range(5)], bar(100.0, 1))
    ids = [f.fill_id for f in cap[FillEvent]]
    assert len(set(ids)) == 5


def test_limit_orders_are_rejected() -> None:
    bus, _, _ = _setup()
    bus.publish(approved(BUY, order_type=OrderType.LIMIT))
    with pytest.raises(ValueError, match="MARKET"):
        bus.run()


@pytest.mark.parametrize("kwargs", [{"slippage_bps": -1}, {"commission_per_share": -0.01}])
def test_negative_costs_raise(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ExecutionSimulator(**kwargs)
