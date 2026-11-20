"""Tests for round-trip trade reconstruction."""

from __future__ import annotations

import pytest

from tests.factories import fill, ts
from trading.events.types import Direction, FillEvent
from trading.metrics.trades import TradeTracker

BUY, SELL = Direction.BUY, Direction.SELL


def _track(*fills: FillEvent) -> TradeTracker:
    tracker = TradeTracker()
    for f in fills:
        tracker.on_fill(f)
    return tracker


def test_long_round_trip_net_of_commission() -> None:
    t = _track(fill(BUY, 100, 10.0, 1.0, i=0), fill(SELL, 100, 12.0, 1.0, i=3))
    (trade,) = t.trades
    assert trade.side == "LONG"
    assert trade.pnl == pytest.approx(200.0 - 2.0)
    assert (trade.entry_time, trade.exit_time) == (ts(0), ts(3))


def test_short_round_trip() -> None:
    (trade,) = _track(fill(SELL, 50, 20.0), fill(BUY, 50, 18.0)).trades
    assert trade.side == "SHORT"
    assert trade.pnl == pytest.approx(100.0)


def test_scaling_in_and_out_is_one_trade() -> None:
    t = _track(
        fill(BUY, 100, 10.0),
        fill(BUY, 100, 12.0),  # avg 11
        fill(SELL, 50, 13.0),  # +100
        fill(SELL, 150, 9.0),  # -300
    )
    (trade,) = t.trades
    assert trade.pnl == pytest.approx(-200.0)


def test_flip_closes_one_trade_and_opens_another_with_split_commission() -> None:
    t = _track(
        fill(BUY, 100, 10.0, 0.0),
        fill(SELL, 300, 11.0, 3.0),  # closes 100 (+100, comm 1), opens -200 (comm 2)
        fill(BUY, 200, 10.0, 2.0),  # covers: +200, comm 2
    )
    assert [tr.side for tr in t.trades] == ["LONG", "SHORT"]
    assert t.trades[0].pnl == pytest.approx(100.0 - 1.0)
    assert t.trades[1].pnl == pytest.approx(200.0 - 2.0 - 2.0)
    assert t.open_trades == 0


def test_open_trade_is_not_reported() -> None:
    t = _track(fill(BUY, 100, 10.0))
    assert t.trades == []
    assert t.open_trades == 1
