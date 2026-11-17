"""Order manager — converts signals into orders that move the position to a target."""

from __future__ import annotations

from trading.bus.event_bus import EventBus
from trading.events.types import (
    Direction,
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    OrderType,
    RiskVetoEvent,
    SignalEvent,
)
from trading.portfolio.position import PositionBook


class OrderManager:
    """Target-position order sizing.

    Each non-HOLD signal sets a target position and the manager orders the
    difference between that target and the *projected* position (filled plus
    still-working orders):

    ============  ==========================  =============================
    Signal        ``allow_short=False``       ``allow_short=True``
    ============  ==========================  =============================
    BUY           target ``+quantity``        target ``+quantity``
    SELL          target ``0`` (exit)         target ``-quantity``
    HOLD          no order                    no order
    ============  ==========================  =============================

    Repeated signals in the same direction therefore never stack exposure, and
    a vetoed order is removed from the projection so the next signal retries.

    Orders are MARKET orders whose ``price`` is the last close, used downstream
    as a reference price (execution fills at the next bar's open).

    Args:
        quantity:    Absolute target position size in shares.
        allow_short: Whether SELL signals may open short positions.
    """

    def __init__(self, quantity: int = 100, allow_short: bool = False) -> None:
        if quantity <= 0:
            raise ValueError(f"quantity must be positive, got {quantity}")
        self.quantity = quantity
        self.allow_short = allow_short
        self._bus: EventBus | None = None
        self._book = PositionBook()
        self._last_close: dict[str, float] = {}
        self._next_id = 1

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(MarketDataEvent, self._on_market_data)
        bus.subscribe(SignalEvent, self._on_signal)
        bus.subscribe(FillEvent, self._book.on_fill)
        bus.subscribe(RiskVetoEvent, self._on_veto)

    # ------------------------------------------------------------------

    def target_for(self, direction: Direction) -> int | None:
        """Target position implied by *direction*, or ``None`` to leave it unchanged."""
        if direction is Direction.BUY:
            return self.quantity
        if direction is Direction.SELL:
            return -self.quantity if self.allow_short else 0
        return None

    def _on_market_data(self, event: MarketDataEvent) -> None:
        self._last_close[event.symbol] = event.close

    def _on_veto(self, event: RiskVetoEvent) -> None:
        self._book.cancel(event.order_id)

    def _on_signal(self, event: SignalEvent) -> None:
        if self._bus is None:
            raise RuntimeError("OrderManager.register() must be called before use")

        target = self.target_for(event.direction)
        if target is None:
            return
        delta = target - self._book.projected(event.symbol)
        if delta == 0:
            return

        order_id = f"O{self._next_id:06d}"
        self._next_id += 1
        self._book.add_working(order_id, event.symbol, delta)
        self._bus.publish(
            OrderEvent(
                symbol=event.symbol,
                timestamp=event.timestamp,
                order_id=order_id,
                order_type=OrderType.MARKET,
                direction=Direction.BUY if delta > 0 else Direction.SELL,
                quantity=abs(delta),
                price=self._last_close.get(event.symbol, 0.0),
            )
        )
