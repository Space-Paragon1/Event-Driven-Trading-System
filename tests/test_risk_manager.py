"""Tests for RiskManager."""

from __future__ import annotations

import pytest

from tests.factories import Capture, fill, order, publish_all, snapshot
from trading.bus.event_bus import EventBus
from trading.events.types import ApprovedOrderEvent, Direction, RiskVetoEvent
from trading.risk.manager import RiskManager

BUY, SELL = Direction.BUY, Direction.SELL


def _run(
    risk: RiskManager, *events: object
) -> tuple[list[ApprovedOrderEvent], list[RiskVetoEvent]]:
    bus = EventBus()
    risk.register(bus)
    cap = Capture(bus, ApprovedOrderEvent, RiskVetoEvent)
    publish_all(bus, *events)
    return cap[ApprovedOrderEvent], cap[RiskVetoEvent]


def test_valid_order_is_approved_unchanged() -> None:
    o = order(BUY, 50)
    (a,), vetoed = _run(RiskManager(), o)
    assert vetoed == []
    assert (a.order_id, a.direction, a.quantity, a.price) == (o.order_id, BUY, 50, o.price)


def test_order_over_position_limit_is_vetoed() -> None:
    approved, (v,) = _run(RiskManager(max_position=500), order(BUY, 600))
    assert approved == []
    assert v.order_id == "O1"
    assert "position limit" in v.reason


def test_position_limit_counts_working_orders() -> None:
    """Two approved-but-unfilled orders must not jointly breach the limit."""
    approved, vetoed = _run(
        RiskManager(max_position=150),
        order(BUY, 100, order_id="O1"),
        order(BUY, 100, order_id="O2"),
    )
    assert [a.order_id for a in approved] == ["O1"]
    assert [v.order_id for v in vetoed] == ["O2"]


def test_position_limit_counts_filled_position() -> None:
    approved, vetoed = _run(
        RiskManager(max_position=150),
        order(BUY, 100, order_id="O1"),
        fill(BUY, 100, order_id="O1"),
        order(BUY, 100, order_id="O2"),
    )
    assert len(approved) == 1
    assert len(vetoed) == 1


def test_drawdown_breaker_vetoes_new_exposure() -> None:
    risk = RiskManager(max_drawdown_pct=5.0, starting_equity=100_000.0)
    approved, (v,) = _run(risk, snapshot(94_000.0), order(BUY, 100))
    assert approved == []
    assert "drawdown" in v.reason
    assert risk.drawdown_pct == pytest.approx(6.0)


def test_drawdown_breaker_still_allows_reducing_orders() -> None:
    approved, vetoed = _run(
        RiskManager(max_drawdown_pct=5.0, starting_equity=100_000.0),
        order(BUY, 100, order_id="O1"),
        fill(BUY, 100, order_id="O1"),
        snapshot(90_000.0, position=100),
        order(SELL, 100, order_id="O2"),
    )
    assert [a.order_id for a in approved] == ["O1", "O2"]
    assert vetoed == []


def test_drawdown_is_measured_from_running_peak() -> None:
    risk = RiskManager(max_drawdown_pct=5.0, starting_equity=100_000.0)
    _, vetoed = _run(risk, snapshot(120_000.0, 0), snapshot(112_000.0, 1), order(BUY, 10))
    assert risk.drawdown_pct == pytest.approx(100 * 8_000 / 120_000)
    assert len(vetoed) == 1


def test_trading_resumes_after_recovery() -> None:
    approved, vetoed = _run(
        RiskManager(max_drawdown_pct=5.0, starting_equity=100_000.0),
        snapshot(90_000.0, 0),
        order(BUY, 10, order_id="O1"),
        snapshot(99_000.0, 1),
        order(BUY, 10, order_id="O2"),
    )
    assert [v.order_id for v in vetoed] == ["O1"]
    assert [a.order_id for a in approved] == ["O2"]


@pytest.mark.parametrize(
    "kwargs", [{"max_position": 0}, {"max_drawdown_pct": 0.0}, {"max_drawdown_pct": 150.0}]
)
def test_invalid_limits_raise(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        RiskManager(**kwargs)  # type: ignore[arg-type]
