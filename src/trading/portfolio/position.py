"""Position accounting shared by the portfolio, order manager, risk and metrics layers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from trading.events.types import FillEvent


@dataclass
class Position:
    """A signed position with average-cost accounting.

    Correctly handles opening, adding to, reducing, closing and *flipping*
    both long and short positions:

    - Fills that open or increase exposure blend into ``avg_cost``.
    - Fills that reduce exposure realize ``(price - avg_cost) * closed_qty``
      (sign-adjusted for shorts) and leave ``avg_cost`` unchanged.
    - A fill that crosses through zero closes the old position and opens the
      remainder at the fill price.

    ``avg_cost`` is ``0.0`` whenever the position is flat.
    """

    quantity: int = 0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0

    def apply(self, signed_qty: int, price: float) -> float:
        """Apply a fill of *signed_qty* shares at *price*; return the P&L it realizes."""
        if signed_qty == 0:
            return 0.0

        before = self.quantity
        after = before + signed_qty
        realized = 0.0

        if before == 0 or (before > 0) == (signed_qty > 0):
            # Opening or increasing exposure: blend the average entry price.
            self.avg_cost = (self.avg_cost * abs(before) + price * abs(signed_qty)) / abs(after)
        else:
            closed = min(abs(signed_qty), abs(before))
            side = 1 if before > 0 else -1
            realized = closed * (price - self.avg_cost) * side
            if after == 0:
                self.avg_cost = 0.0
            elif (after > 0) != (before > 0):
                self.avg_cost = price  # flipped: the remainder was opened at this fill
            # Partial reduction: the remaining shares keep their entry price.

        self.quantity = after
        self.realized_pnl += realized
        return realized

    def unrealized_pnl(self, mark: float) -> float:
        """Open P&L if the position were marked at *mark*."""
        return (mark - self.avg_cost) * self.quantity


class PositionBook:
    """Filled positions plus working (submitted but unfilled) orders, per symbol.

    With next-bar execution, an order is still working when the next signal
    arrives. Order sizing and pre-trade risk must therefore use
    :meth:`projected` (filled + working) or they will double-count.

    Partial fills are not modelled: a fill completes its order.
    """

    def __init__(self) -> None:
        self._filled: defaultdict[str, int] = defaultdict(int)
        self._working: dict[str, tuple[str, int]] = {}  # order_id -> (symbol, signed qty)

    def add_working(self, order_id: str, symbol: str, signed_qty: int) -> None:
        self._working[order_id] = (symbol, signed_qty)

    def cancel(self, order_id: str) -> None:
        self._working.pop(order_id, None)

    def on_fill(self, fill: FillEvent) -> None:
        self._working.pop(fill.order_id, None)
        self._filled[fill.symbol] += fill.signed_quantity

    def filled(self, symbol: str) -> int:
        return self._filled.get(symbol, 0)

    def projected(self, symbol: str) -> int:
        working = sum(qty for sym, qty in self._working.values() if sym == symbol)
        return self.filled(symbol) + working
