"""Tests for EventBus."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from trading.bus.event_bus import EventBus


@dataclass
class _FooEvent:
    value: int


@dataclass
class _BarEvent:
    label: str


def test_single_subscriber_receives_event() -> None:
    bus = EventBus()
    received: list[_FooEvent] = []
    bus.subscribe(_FooEvent, received.append)

    bus.publish(_FooEvent(value=1))
    bus.run()

    assert len(received) == 1
    assert received[0].value == 1


def test_multiple_subscribers_all_receive_event() -> None:
    bus = EventBus()
    box_a: list[_FooEvent] = []
    box_b: list[_FooEvent] = []
    bus.subscribe(_FooEvent, box_a.append)
    bus.subscribe(_FooEvent, box_b.append)

    bus.publish(_FooEvent(value=7))
    bus.run()

    assert len(box_a) == 1
    assert len(box_b) == 1


def test_unrelated_subscriber_does_not_receive_event() -> None:
    bus = EventBus()
    bar_received: list[_BarEvent] = []
    bus.subscribe(_BarEvent, bar_received.append)

    bus.publish(_FooEvent(value=99))
    bus.run()

    assert bar_received == []


def test_events_dispatched_in_fifo_order() -> None:
    bus = EventBus()
    order: list[int] = []
    bus.subscribe(_FooEvent, lambda e: order.append(e.value))

    for i in range(5):
        bus.publish(_FooEvent(value=i))
    bus.run()

    assert order == [0, 1, 2, 3, 4]


def test_max_events_limits_processing() -> None:
    bus = EventBus()
    received: list[_FooEvent] = []
    bus.subscribe(_FooEvent, received.append)

    for i in range(10):
        bus.publish(_FooEvent(value=i))
    bus.run(max_events=3)

    assert len(received) == 3


def test_publish_unknown_type_is_safe() -> None:
    """Publishing an event with no subscribers should not raise."""
    bus = EventBus()
    bus.publish(_FooEvent(value=0))  # no subscriber registered
    bus.run()  # should complete without error
