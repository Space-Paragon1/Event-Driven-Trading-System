"""Risk manager — pre-trade checks between order generation and execution."""

from __future__ import annotations

from trading.bus.event_bus import EventBus
from trading.events.types import (
    ApprovedOrderEvent,
    FillEvent,
    OrderEvent,
    PortfolioUpdateEvent,
    RiskVetoEvent,
)
from trading.portfolio.position import PositionBook


class RiskManager:
    """Approves or vetoes every :class:`OrderEvent`.

    Only :class:`ApprovedOrderEvent` reaches the execution simulator, so this
    is the single choke point for pre-trade risk.

    Checks, in order. Both apply only to orders that *increase* absolute
    exposure, so a strategy can always reduce or close a position:

    1. **Position limit.** The projected position (filled + approved-but-unfilled
       + this order) must satisfy ``|position| <= max_position``.
    2. **Drawdown circuit breaker.** Once equity has fallen more than
       ``max_drawdown_pct`` below its running peak, new exposure is refused.
       It re-arms only if equity climbs back within the limit, which an open
       position can do but a flat book cannot. In practice it acts as a kill
       switch for the rest of the run.

    Args:
        max_position:     Maximum absolute shares per symbol.
        max_drawdown_pct: Maximum drawdown from peak equity, in percent.
        starting_equity:  Initial peak equity.
    """

    def __init__(
        self,
        max_position: int = 500,
        max_drawdown_pct: float = 10.0,
        starting_equity: float = 100_000.0,
    ) -> None:
        if max_position <= 0:
            raise ValueError(f"max_position must be positive, got {max_position}")
        if not 0.0 < max_drawdown_pct <= 100.0:
            raise ValueError(f"max_drawdown_pct must be in (0, 100], got {max_drawdown_pct}")
        self.max_position = max_position
        self.max_drawdown_pct = max_drawdown_pct
        self._bus: EventBus | None = None
        self._book = PositionBook()
        self._peak_equity = starting_equity
        self._equity = starting_equity

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(OrderEvent, self._on_order)
        bus.subscribe(FillEvent, self._book.on_fill)
        bus.subscribe(PortfolioUpdateEvent, self._on_portfolio_update)

    @property
    def drawdown_pct(self) -> float:
        """Current drawdown from peak equity, in percent."""
        if self._peak_equity <= 0:
            return 0.0
        return max(0.0, (self._peak_equity - self._equity) / self._peak_equity * 100.0)

    # ------------------------------------------------------------------

    def _on_portfolio_update(self, event: PortfolioUpdateEvent) -> None:
        self._equity = event.equity
        self._peak_equity = max(self._peak_equity, event.equity)

    def _on_order(self, event: OrderEvent) -> None:
        if self._bus is None:
            raise RuntimeError("RiskManager.register() must be called before use")

        current = self._book.projected(event.symbol)
        new = current + event.signed_quantity
        increases_exposure = abs(new) > abs(current)

        reason: str | None = None
        if increases_exposure and abs(new) > self.max_position:
            reason = f"position limit: |{new}| > {self.max_position}"
        elif increases_exposure and self.drawdown_pct > self.max_drawdown_pct:
            reason = f"drawdown breaker: {self.drawdown_pct:.2f}% > {self.max_drawdown_pct:g}%"

        if reason is not None:
            self._bus.publish(
                RiskVetoEvent(
                    symbol=event.symbol,
                    timestamp=event.timestamp,
                    order_id=event.order_id,
                    reason=reason,
                )
            )
            return

        self._book.add_working(event.order_id, event.symbol, event.signed_quantity)
        self._bus.publish(
            ApprovedOrderEvent(
                symbol=event.symbol,
                timestamp=event.timestamp,
                order_id=event.order_id,
                order_type=event.order_type,
                direction=event.direction,
                quantity=event.quantity,
                price=event.price,
            )
        )
