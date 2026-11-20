"""Tests for EventBus."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from trading.bus.event_bus import EventBus


@dataclass
class Foo:
    value: int


@dataclass
class Bar:
    label: str


def test_single_subscriber_receives_event() -> None:
    bus = EventBus()
    received: list[Foo] = []
    bus.subscribe(Foo, received.append)
    bus.publish(Foo(1))
    bus.run()
    assert received == [Foo(1)]


def test_multiple_subscribers_all_receive_event_in_subscription_order() -> None:
    bus = EventBus()
    calls: list[str] = []
    bus.subscribe(Foo, lambda _: calls.append("a"))
    bus.subscribe(Foo, lambda _: calls.append("b"))
    bus.publish(Foo(7))
    bus.run()
    assert calls == ["a", "b"]


def test_unrelated_subscriber_does_not_receive_event() -> None:
    bus = EventBus()
    bars: list[Bar] = []
    bus.subscribe(Bar, bars.append)
    bus.publish(Foo(99))
    bus.run()
    assert bars == []


def test_events_dispatched_in_fifo_order() -> None:
    bus = EventBus()
    seen: list[int] = []
    bus.subscribe(Foo, lambda e: seen.append(e.value))
    for i in range(5):
        bus.publish(Foo(i))
    bus.run()
    assert seen == [0, 1, 2, 3, 4]


def test_dispatch_is_breadth_first() -> None:
    """Events published by handlers are delivered after the current event's handlers finish."""
    bus = EventBus()
    log: list[str] = []

    def on_foo(e: Foo) -> None:
        log.append(f"foo{e.value}")
        bus.publish(Bar(f"from{e.value}"))

    bus.subscribe(Foo, on_foo)
    bus.subscribe(Bar, lambda e: log.append(e.label))
    bus.publish(Foo(1))
    bus.publish(Foo(2))
    bus.run()
    assert log == ["foo1", "foo2", "from1", "from2"]


def test_run_drains_cascades_and_returns_count() -> None:
    bus = EventBus()
    bus.subscribe(Foo, lambda e: bus.publish(Bar("x")) if e.value else None)
    bus.publish(Foo(1))
    assert bus.run() == 2
    assert bus.pending == 0


def test_max_events_limits_processing() -> None:
    bus = EventBus()
    received: list[Foo] = []
    bus.subscribe(Foo, received.append)
    for i in range(10):
        bus.publish(Foo(i))
    assert bus.run(max_events=3) == 3
    assert len(received) == 3
    assert bus.pending == 7


def test_publish_without_subscribers_is_safe() -> None:
    bus = EventBus()
    bus.publish(Foo(0))
    assert bus.run() == 1


def test_dispatch_matches_exact_type_only() -> None:
    @dataclass
    class SubFoo(Foo):
        pass

    bus = EventBus()
    received: list[Foo] = []
    bus.subscribe(Foo, received.append)
    bus.publish(SubFoo(1))
    bus.run()
    assert received == []


def test_handler_exceptions_propagate() -> None:
    bus = EventBus()

    def boom(_: Foo) -> None:
        raise RuntimeError("handler failed")

    bus.subscribe(Foo, boom)
    bus.publish(Foo(1))
    with pytest.raises(RuntimeError, match="handler failed"):
        bus.run()
