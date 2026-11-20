"""Synchronous, single-threaded publish/subscribe event bus."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class Component(Protocol):
    """Interface every pipeline component satisfies."""

    def register(self, bus: EventBus) -> None: ...


class EventBus:
    """FIFO publish/subscribe dispatcher.

    :meth:`publish` enqueues an event; :meth:`run` drains the queue, including
    any events that handlers publish while it runs.

    Dispatch guarantees:

    - **Breadth-first.** Every handler for an event runs before any event those
      handlers published is delivered.
    - **Deterministic.** Handlers for one event type run in subscription order.
    - **Fail-fast.** Handler exceptions propagate out of :meth:`run`. A backtest
      that silently skips a broken component is worse than one that stops.

    Usage::

        bus = EventBus()
        bus.subscribe(MarketDataEvent, strategy.on_bar)
        bus.publish(bar)
        bus.run()
    """

    def __init__(self) -> None:
        self._queue: deque[object] = deque()
        self._handlers: defaultdict[type, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: type[T], handler: Callable[[T], None]) -> None:
        """Call *handler* for every published event whose type is exactly *event_type*."""
        self._handlers[event_type].append(handler)

    def publish(self, event: object) -> None:
        """Enqueue *event* for dispatch on the next :meth:`run`."""
        self._queue.append(event)

    @property
    def pending(self) -> int:
        """Number of events waiting to be dispatched."""
        return len(self._queue)

    def run(self, max_events: int | None = None) -> int:
        """Dispatch queued events until the queue is empty.

        Args:
            max_events: Stop after dispatching this many events. ``None`` runs
                until the queue is empty.

        Returns:
            The number of events dispatched.
        """
        processed = 0
        while self._queue and (max_events is None or processed < max_events):
            event = self._queue.popleft()
            for handler in self._handlers.get(type(event), ()):
                handler(event)
            processed += 1
        return processed
