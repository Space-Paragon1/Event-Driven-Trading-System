"""Synchronous in-process event bus."""

from __future__ import annotations

import queue
from collections import defaultdict
from typing import Any, Callable, Protocol


class Component(Protocol):
    """Interface every pipeline component must satisfy."""

    def register(self, bus: EventBus) -> None: ...


class EventBus:
    """Pub/sub hub backed by a FIFO queue.

    Usage::

        bus = EventBus()
        bus.subscribe(MarketDataEvent, my_handler)
        bus.publish(MarketDataEvent(...))
        bus.run()
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[Any] = queue.Queue()
        self._handlers: dict[type, list[Callable[[Any], None]]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        """Register *handler* to be called whenever *event_type* is published."""
        self._handlers[event_type].append(handler)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(self, event: Any) -> None:
        """Enqueue *event* for dispatch."""
        self._queue.put(event)

    # ------------------------------------------------------------------
    # Dispatch loop
    # ------------------------------------------------------------------

    def run(self, max_events: int | None = None) -> None:
        """Drain the queue and dispatch each event to its subscribers.

        Args:
            max_events: Stop after processing this many events. ``None``
                        means run until the queue is empty.
        """
        processed = 0
        while not self._queue.empty():
            if max_events is not None and processed >= max_events:
                break
            event = self._queue.get_nowait()
            for handler in self._handlers.get(type(event), []):
                handler(event)
            processed += 1
