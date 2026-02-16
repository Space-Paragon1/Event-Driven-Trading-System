"""Risk manager — intercepts orders and vetoes rule-breaking ones."""

from __future__ import annotations

from trading.bus.event_bus import EventBus
from trading.events.types import (
    ApprovedOrderEvent,
    Direction,
    OrderEvent,
    PortfolioUpdateEvent,
    RiskVetoEvent,
)


class RiskManager:
    """Sits between :class:`~trading.order_manager.manager.OrderManager` and
    :class:`~trading.execution.simulator.ExecutionSimulator`.

    Subscribes to :class:`~trading.events.types.OrderEvent` and either:

    - Publishes :class:`~trading.events.types.ApprovedOrderEvent` if the order
      passes all checks, or
    - Publishes :class:`~trading.events.types.RiskVetoEvent` if it fails.

    Also subscribes to :class:`~trading.events.types.PortfolioUpdateEvent` to
    keep track of current equity and positions.

    Risk checks:
    1. **Position limit** — ``abs(current_position + order_qty) <= max_position``
    2. **Max drawdown** — equity must not have fallen more than *max_drawdown_pct*
       from its peak.

    Args:
        max_position:      Maximum absolute share exposure per symbol.
        max_drawdown_pct:  Maximum allowed drawdown from peak equity (percent).
        starting_equity:   Starting equity used to initialise the peak.
    """

    def __init__(
        self,
        max_position: int = 500,
        max_drawdown_pct: float = 10.0,
        starting_equity: float = 100_000.0,
    ) -> None:
        self.max_position = max_position
        self.max_drawdown_pct = max_drawdown_pct
        self._bus: EventBus | None = None
        self._positions: dict[str, int] = {}   # symbol → net shares
        self._peak_equity: float = starting_equity
        self._current_equity: float = starting_equity

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(OrderEvent, self._on_order)
        bus.subscribe(PortfolioUpdateEvent, self._on_portfolio_update)

    # ------------------------------------------------------------------

    def _on_portfolio_update(self, event: PortfolioUpdateEvent) -> None:
        self._current_equity = event.equity
        if event.equity > self._peak_equity:
            self._peak_equity = event.equity
        # sync position from portfolio
        self._positions[event.symbol] = event.position

    def _on_order(self, event: OrderEvent) -> None:
        assert self._bus is not None

        signed_qty = event.quantity if event.direction is Direction.BUY else -event.quantity
        current = self._positions.get(event.symbol, 0)
        new_position = current + signed_qty

        # Check 1: position limit
        if abs(new_position) > self.max_position:
            self._bus.publish(
                RiskVetoEvent(
                    order_id=event.order_id,
                    symbol=event.symbol,
                    timestamp=event.timestamp,
                    reason=f"position limit exceeded: |{new_position}| > {self.max_position}",
                )
            )
            return

        # Check 2: max drawdown
        if self._peak_equity > 0:
            drawdown_pct = (self._peak_equity - self._current_equity) / self._peak_equity * 100
            if drawdown_pct > self.max_drawdown_pct:
                self._bus.publish(
                    RiskVetoEvent(
                        order_id=event.order_id,
                        symbol=event.symbol,
                        timestamp=event.timestamp,
                        reason=f"max drawdown exceeded: {drawdown_pct:.2f}% > {self.max_drawdown_pct}%",
                    )
                )
                return

        # All checks passed
        self._bus.publish(
            ApprovedOrderEvent(
                order_id=event.order_id,
                symbol=event.symbol,
                timestamp=event.timestamp,
                order_type=event.order_type,
                direction=event.direction,
                quantity=event.quantity,
                price=event.price,
            )
        )
