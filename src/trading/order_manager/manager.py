"""Order manager — converts non-HOLD signals into market orders."""

from __future__ import annotations

import uuid

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, MarketDataEvent, OrderEvent, OrderType, SignalEvent

_DEFAULT_QUANTITY = 100


class OrderManager:
    """Subscribes to :class:`~trading.events.types.SignalEvent` and emits a
    :class:`~trading.events.types.OrderEvent` for every BUY or SELL signal.

    Also subscribes to :class:`~trading.events.types.MarketDataEvent` to track
    the latest close price per symbol, which is used as the reference price in
    each order (enables accurate slippage simulation downstream).

    HOLD signals are silently discarded.

    Args:
        quantity: Fixed lot size for every order (default ``100``).
    """

    def __init__(self, quantity: int = _DEFAULT_QUANTITY) -> None:
        self.quantity = quantity
        self._bus: EventBus | None = None
        self._last_price: dict[str, float] = {}

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(MarketDataEvent, self._on_market_data)
        bus.subscribe(SignalEvent, self._on_signal)

    # ------------------------------------------------------------------

    def _on_market_data(self, event: MarketDataEvent) -> None:
        self._last_price[event.symbol] = event.close

    def _on_signal(self, event: SignalEvent) -> None:
        assert self._bus is not None, "register() must be called before emitting events"
        if event.direction is Direction.HOLD:
            return

        ref_price = self._last_price.get(event.symbol, 0.0)

        self._bus.publish(
            OrderEvent(
                order_id=str(uuid.uuid4()),
                symbol=event.symbol,
                timestamp=event.timestamp,
                order_type=OrderType.MARKET,
                direction=event.direction,
                quantity=self.quantity,
                price=ref_price,
            )
        )
