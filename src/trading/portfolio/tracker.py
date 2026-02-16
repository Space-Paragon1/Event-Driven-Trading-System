"""Portfolio tracker — maintains positions, cash, and P&L."""

from __future__ import annotations

from trading.bus.event_bus import EventBus
from trading.events.types import Direction, FillEvent, MarketDataEvent, PortfolioUpdateEvent


class PortfolioTracker:
    """Subscribes to :class:`~trading.events.types.FillEvent` and
    :class:`~trading.events.types.MarketDataEvent` to maintain a real-time
    view of the portfolio.

    After each fill it publishes a
    :class:`~trading.events.types.PortfolioUpdateEvent` with current positions,
    P&L, cash, and total equity.

    Positions are per symbol.  Average cost is updated using a weighted average
    on buys.  Realized P&L is computed on position reductions (sells).

    Args:
        starting_cash: Initial cash balance (default ``$100,000``).
    """

    def __init__(self, starting_cash: float = 100_000.0) -> None:
        self.cash = starting_cash
        self._bus: EventBus | None = None
        self._positions: dict[str, int] = {}        # symbol → net shares
        self._avg_cost: dict[str, float] = {}       # symbol → avg cost/share
        self._realized_pnl: dict[str, float] = {}   # symbol → cumulative realized
        self._last_price: dict[str, float] = {}     # symbol → most recent close

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(FillEvent, self._on_fill)
        bus.subscribe(MarketDataEvent, self._on_market_data)

    # ------------------------------------------------------------------

    def _on_market_data(self, event: MarketDataEvent) -> None:
        self._last_price[event.symbol] = event.close

    def _on_fill(self, event: FillEvent) -> None:
        assert self._bus is not None

        sym = event.symbol
        qty = event.quantity
        price = event.fill_price
        comm = event.commission

        pos = self._positions.get(sym, 0)
        avg = self._avg_cost.get(sym, 0.0)
        realized = self._realized_pnl.get(sym, 0.0)

        if event.direction is Direction.BUY:
            total_cost = avg * pos + price * qty
            pos += qty
            avg = total_cost / pos if pos else 0.0
            self.cash -= price * qty + comm
        else:  # SELL
            realized += (price - avg) * qty
            pos -= qty
            self.cash += price * qty - comm
            if pos == 0:
                avg = 0.0

        self._positions[sym] = pos
        self._avg_cost[sym] = avg
        self._realized_pnl[sym] = realized

        last = self._last_price.get(sym, price)
        unrealized = (last - avg) * pos if pos else 0.0

        equity = self.cash + sum(
            self._positions.get(s, 0) * self._last_price.get(s, self._avg_cost.get(s, 0.0))
            for s in self._positions
        )

        self._bus.publish(
            PortfolioUpdateEvent(
                symbol=sym,
                timestamp=event.timestamp,
                position=pos,
                avg_cost=round(avg, 4),
                realized_pnl=round(realized, 4),
                unrealized_pnl=round(unrealized, 4),
                cash=round(self.cash, 4),
                equity=round(equity, 4),
            )
        )
