"""Tests for MACrossoverStrategy."""

from __future__ import annotations

import pytest

from tests.factories import Capture, bar, bars, publish_all
from trading.bus.event_bus import EventBus
from trading.events.types import Direction, SignalEvent
from trading.signal.ma_crossover import MACrossoverStrategy


def _signals(
    closes: list[float], fast: int = 3, slow: int = 5, symbol: str = "X"
) -> list[SignalEvent]:
    bus = EventBus()
    MACrossoverStrategy(fast=fast, slow=slow).register(bus)
    cap = Capture(bus, SignalEvent)
    publish_all(bus, *bars(closes, symbol=symbol))
    return cap[SignalEvent]


def _directions(closes: list[float], **kw: int) -> list[Direction]:
    return [s.direction for s in _signals(closes, **kw)]  # type: ignore[arg-type]


def test_hold_during_warmup() -> None:
    assert _directions([100.0, 101.0, 102.0, 103.0]) == [Direction.HOLD] * 4


def test_buy_on_the_upward_crossover_bar() -> None:
    #           warm-up (fast < slow) ........  cross at index 5
    closes = [100.0, 99.0, 98.0, 97.0, 96.0, 110.0, 120.0, 130.0]
    dirs = _directions(closes)
    assert dirs.index(Direction.BUY) == 5
    assert dirs.count(Direction.BUY) == 1


def test_sell_on_the_downward_crossover_bar() -> None:
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 80.0, 60.0, 40.0]
    dirs = _directions(closes)
    assert dirs.index(Direction.SELL) == 5
    assert Direction.BUY not in dirs


def test_no_signal_without_a_cross() -> None:
    assert set(_directions([float(i) for i in range(1, 30)])) == {Direction.HOLD}


def test_strength_in_unit_interval() -> None:
    for s in _signals([float(i) ** 2 for i in range(1, 30)]):
        assert 0.0 <= s.strength <= 1.0


def test_one_signal_per_bar_with_bar_timestamp() -> None:
    closes = [float(i) for i in range(1, 20)]
    signals = _signals(closes)
    assert [s.timestamp for s in signals] == [b.timestamp for b in bars(closes)]


def test_symbols_are_tracked_independently() -> None:
    bus = EventBus()
    MACrossoverStrategy(fast=2, slow=3).register(bus)
    cap = Capture(bus, SignalEvent)
    # Interleave two symbols; only MSFT's series crosses.
    events = []
    for i, (a, m) in enumerate(zip([10, 10, 10, 10, 10], [10, 9, 8, 12, 14], strict=True)):
        events += [bar(float(a), i, symbol="AAPL"), bar(float(m), i, symbol="MSFT")]
    publish_all(bus, *events)
    by_symbol = {
        sym: [s.direction for s in cap[SignalEvent] if s.symbol == sym] for sym in ("AAPL", "MSFT")
    }
    assert Direction.BUY not in by_symbol["AAPL"]
    assert Direction.BUY in by_symbol["MSFT"]


@pytest.mark.parametrize(("fast", "slow"), [(10, 5), (5, 5), (0, 5)])
def test_invalid_windows_raise(fast: int, slow: int) -> None:
    with pytest.raises(ValueError, match="fast"):
        MACrossoverStrategy(fast=fast, slow=slow)


def test_unregistered_strategy_raises() -> None:
    strategy = MACrossoverStrategy()
    with pytest.raises(RuntimeError, match="register"):
        strategy._on_market_data(bar(1.0))
