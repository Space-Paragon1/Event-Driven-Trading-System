"""Tests for PortfolioTracker."""

from __future__ import annotations

import pytest

from tests.factories import Capture, bar, end_of_bar, fill, publish_all
from trading.bus.event_bus import EventBus
from trading.events.types import Direction, PortfolioUpdateEvent
from trading.portfolio.tracker import PortfolioTracker

CASH = 100_000.0


def _run(*events: object) -> tuple[PortfolioTracker, list[PortfolioUpdateEvent]]:
    bus = EventBus()
    tracker = PortfolioTracker(starting_cash=CASH)
    tracker.register(bus)
    cap = Capture(bus, PortfolioUpdateEvent)
    publish_all(bus, *events)
    return tracker, cap[PortfolioUpdateEvent]


def test_snapshot_published_only_at_end_of_bar() -> None:
    _, updates = _run(bar(150.0), fill(Direction.BUY))
    assert updates == []
    _, updates = _run(bar(150.0), fill(Direction.BUY), end_of_bar())
    assert len(updates) == 1


def test_buy_debits_cash_including_commission() -> None:
    tracker, _ = _run(fill(Direction.BUY, 100, 150.0, commission=1.0))
    assert tracker.cash == pytest.approx(CASH - 15_000.0 - 1.0)


def test_round_trip_cash_and_realized_pnl() -> None:
    tracker, updates = _run(
        bar(155.0),
        fill(Direction.BUY, 100, 150.0, commission=1.0),
        fill(Direction.SELL, 100, 155.0, commission=1.0),
        end_of_bar(),
    )
    u = updates[-1]
    assert u.position == 0
    assert u.realized_pnl == pytest.approx(500.0)
    assert tracker.cash == pytest.approx(CASH + 500.0 - 2.0)


def test_snapshot_marks_to_last_close() -> None:
    _, updates = _run(bar(160.0), fill(Direction.BUY, 100, 150.0), end_of_bar())
    u = updates[0]
    assert u.unrealized_pnl == pytest.approx(1_000.0)
    assert u.equity == pytest.approx(CASH - 15_000.0 + 16_000.0)


def test_short_position_accounting() -> None:
    """Regression: shorting from flat used to report the full notional as realized P&L."""
    _, updates = _run(bar(145.0), fill(Direction.SELL, 100, 150.0), end_of_bar())
    u = updates[0]
    assert u.position == -100
    assert u.avg_cost == pytest.approx(150.0)
    assert u.realized_pnl == 0.0
    assert u.unrealized_pnl == pytest.approx(500.0)
    assert u.cash == pytest.approx(CASH + 15_000.0)
    assert u.equity == pytest.approx(CASH + 500.0)


def test_equity_identity_holds_every_bar() -> None:
    events: list[object] = []
    closes = [100.0, 103.0, 98.0, 110.0, 95.0]
    trades = {0: (Direction.BUY, 200), 2: (Direction.SELL, 300), 3: (Direction.BUY, 100)}
    for i, close in enumerate(closes):
        events.append(bar(close, i))
        if i in trades:
            d, q = trades[i]
            events.append(fill(d, q, close, commission=0.5, i=i, order_id=f"O{i}"))
        events.append(end_of_bar(i))
    _, updates = _run(*events)

    assert len(updates) == len(closes)
    for u, close in zip(updates, closes, strict=True):
        assert u.equity == pytest.approx(u.cash + u.position * close)
