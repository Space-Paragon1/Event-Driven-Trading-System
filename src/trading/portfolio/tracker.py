"""Portfolio tracker — cash, positions and P&L, marked to market every bar."""

from __future__ import annotations

from trading.bus.event_bus import EventBus
from trading.events.types import EndOfBarEvent, FillEvent, MarketDataEvent, PortfolioUpdateEvent
from trading.portfolio.position import Position


class PortfolioTracker:
    """Source of truth for cash, positions and equity.

    Subscribes to:

    - :class:`MarketDataEvent`: records the latest close as the mark price.
    - :class:`FillEvent`: updates cash and the position (long or short).
    - :class:`EndOfBarEvent`: publishes a :class:`PortfolioUpdateEvent`
      snapshot marked at the bar's close. Exactly one per bar, after every fill
      that occurred during it.

    Args:
        starting_cash: Initial cash balance.
    """

    def __init__(self, starting_cash: float = 100_000.0) -> None:
        self.cash = starting_cash
        self._bus: EventBus | None = None
        self._positions: dict[str, Position] = {}
        self._marks: dict[str, float] = {}

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(MarketDataEvent, self._on_market_data)
        bus.subscribe(FillEvent, self._on_fill)
        bus.subscribe(EndOfBarEvent, self._on_end_of_bar)

    # ------------------------------------------------------------------

    def position(self, symbol: str) -> Position:
        return self._positions.setdefault(symbol, Position())

    @property
    def equity(self) -> float:
        """Cash plus the market value of every open position."""
        return self.cash + sum(
            pos.quantity * self._marks.get(sym, pos.avg_cost)
            for sym, pos in self._positions.items()
        )

    # ------------------------------------------------------------------

    def _on_market_data(self, event: MarketDataEvent) -> None:
        self._marks[event.symbol] = event.close

    def _on_fill(self, event: FillEvent) -> None:
        self.position(event.symbol).apply(event.signed_quantity, event.fill_price)
        self.cash -= event.signed_quantity * event.fill_price + event.commission

    def _on_end_of_bar(self, event: EndOfBarEvent) -> None:
        if self._bus is None:
            raise RuntimeError("PortfolioTracker.register() must be called before use")
        pos = self.position(event.symbol)
        mark = self._marks.get(event.symbol, pos.avg_cost)
        self._bus.publish(
            PortfolioUpdateEvent(
                symbol=event.symbol,
                timestamp=event.timestamp,
                position=pos.quantity,
                avg_cost=round(pos.avg_cost, 6),
                realized_pnl=round(pos.realized_pnl, 6),
                unrealized_pnl=round(pos.unrealized_pnl(mark), 6),
                cash=round(self.cash, 6),
                equity=round(self.equity, 6),
            )
        )
