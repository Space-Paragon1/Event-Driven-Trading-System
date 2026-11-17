"""Tests for RSIStrategy."""

from __future__ import annotations

import pytest

from tests.factories import Capture, bars, publish_all
from trading.bus.event_bus import EventBus
from trading.events.types import Direction, SignalEvent
from trading.signal.rsi import RSIStrategy


def _signals(closes: list[float], period: int = 5, **kw: float) -> list[SignalEvent]:
    bus = EventBus()
    RSIStrategy(period=period, **kw).register(bus)
    cap = Capture(bus, SignalEvent)
    publish_all(bus, *bars(closes))
    return cap[SignalEvent]


def _directions(closes: list[float], period: int = 5) -> list[Direction]:
    return [s.direction for s in _signals(closes, period)]


def test_hold_during_warmup() -> None:
    # period=5 needs 6 prices before the first RSI value.
    assert _directions([100.0, 99.0, 98.0, 97.0, 96.0]) == [Direction.HOLD] * 5


def test_hold_when_flat() -> None:
    assert set(_directions([100.0] * 20)) == {Direction.HOLD}


def test_buy_when_rsi_crosses_into_oversold() -> None:
    closes = [100.0] * 6 + [80.0, 70.0, 60.0, 55.0, 50.0, 55.0, 60.0, 65.0]
    dirs = _directions(closes)
    assert dirs.index(Direction.BUY) == 6  # first bar of the sell-off
    assert dirs.count(Direction.BUY) == 1  # stays oversold: no repeated signals


def test_sell_when_rsi_crosses_into_overbought() -> None:
    # Wilder RSI(5): 0 -> 38.5 -> 65.2 -> 80.8, crossing 70 on the last bar.
    closes = [100.0, 98.0, 96.0, 94.0, 92.0, 90.0, 95.0, 103.0, 115.0]
    dirs = _directions(closes)
    assert dirs[-1] is Direction.SELL
    assert dirs.count(Direction.SELL) == 1


def test_strength_in_unit_interval() -> None:
    for s in _signals([float(x) for x in range(100, 130)]):
        assert 0.0 <= s.strength <= 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"period": 1},
        {"oversold": 70.0, "overbought": 30.0},
        {"oversold": -1.0},
        {"overbought": 101.0},
    ],
)
def test_invalid_parameters_raise(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        RSIStrategy(**kwargs)  # type: ignore[arg-type]
