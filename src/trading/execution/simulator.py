"""Execution simulator — fills approved orders on the next bar, with costs."""

from __future__ import annotations

from collections import defaultdict

from trading.bus.event_bus import EventBus
from trading.events.types import (
    ApprovedOrderEvent,
    Direction,
    FillEvent,
    MarketDataEvent,
    OrderType,
)


class ExecutionSimulator:
    """Fills approved market orders at the **open of the next bar**.

    A strategy reacts to bar *t* after it closes, so the earliest price it
    could realistically trade at is bar *t+1*'s open. Filling at bar *t*'s
    close (a common shortcut) uses information that was not available when
    the order was sent, which is look-ahead bias.

    Costs:

    - **Slippage.** ``slippage_bps`` basis points, always against the trader:
      buys fill above the open and sells below it.
    - **Commission.** ``commission_per_share * quantity``.

    Orders still working when the data ends are never filled; see
    :attr:`working_orders`.

    Args:
        slippage_bps:          Adverse slippage in basis points (1 bp = 0.01 %).
        commission_per_share:  Commission per share, in currency units.
    """

    def __init__(self, slippage_bps: float = 1.0, commission_per_share: float = 0.01) -> None:
        if slippage_bps < 0:
            raise ValueError(f"slippage_bps must be non-negative, got {slippage_bps}")
        if commission_per_share < 0:
            raise ValueError(
                f"commission_per_share must be non-negative, got {commission_per_share}"
            )
        self.slippage_bps = slippage_bps
        self.commission_per_share = commission_per_share
        self._bus: EventBus | None = None
        self._working: defaultdict[str, list[ApprovedOrderEvent]] = defaultdict(list)
        self._next_id = 1

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(ApprovedOrderEvent, self._on_approved)
        bus.subscribe(MarketDataEvent, self._on_bar)

    @property
    def working_orders(self) -> int:
        """Approved orders waiting for the next bar."""
        return sum(len(orders) for orders in self._working.values())

    def fill_price(self, direction: Direction, open_price: float) -> float:
        """Execution price for a market order against *open_price*."""
        slip = self.slippage_bps / 10_000.0
        adj = 1.0 + slip if direction is Direction.BUY else 1.0 - slip
        return round(open_price * adj, 4)

    # ------------------------------------------------------------------

    def _on_approved(self, event: ApprovedOrderEvent) -> None:
        if event.order_type is not OrderType.MARKET:
            raise ValueError(
                f"ExecutionSimulator supports MARKET orders only (got {event.order_type.name})"
            )
        self._working[event.symbol].append(event)

    def _on_bar(self, bar: MarketDataEvent) -> None:
        orders = self._working.pop(bar.symbol, None)
        if not orders:
            return
        if self._bus is None:
            raise RuntimeError("ExecutionSimulator.register() must be called before use")

        for order in orders:
            fill_id = f"F{self._next_id:06d}"
            self._next_id += 1
            self._bus.publish(
                FillEvent(
                    symbol=order.symbol,
                    timestamp=bar.timestamp,
                    fill_id=fill_id,
                    order_id=order.order_id,
                    direction=order.direction,
                    quantity=order.quantity,
                    fill_price=self.fill_price(order.direction, bar.open),
                    commission=round(order.quantity * self.commission_per_share, 4),
                )
            )
