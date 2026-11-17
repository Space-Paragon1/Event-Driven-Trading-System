"""Round-trip trade reconstruction from a stream of fills."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from trading.events.types import FillEvent
from trading.portfolio.position import Position


@dataclass(frozen=True, slots=True)
class Trade:
    """A completed round trip: flat → open → flat (or through a flip).

    ``pnl`` is net of every commission paid while the trade was open. A fill
    that flips the position has its commission split pro rata between the
    trade it closes and the trade it opens.
    """

    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_time: datetime
    exit_time: datetime
    pnl: float


@dataclass
class _OpenTrade:
    side: str
    entry_time: datetime
    pnl: float = 0.0


class TradeTracker:
    """Feeds fills through position accounting and records closed round trips."""

    def __init__(self) -> None:
        self.trades: list[Trade] = []
        self._positions: dict[str, Position] = {}
        self._open: dict[str, _OpenTrade] = {}

    def on_fill(self, fill: FillEvent) -> None:
        pos = self._positions.setdefault(fill.symbol, Position())
        before = pos.quantity
        signed = fill.signed_quantity
        realized = pos.apply(signed, fill.fill_price)
        after = pos.quantity

        reducing = before != 0 and (before > 0) != (signed > 0)
        closed_qty = min(abs(signed), abs(before)) if reducing else 0
        closing_comm = fill.commission * closed_qty / abs(signed)
        opening_comm = fill.commission - closing_comm

        trade = self._open.get(fill.symbol)
        if trade is not None:
            trade.pnl += realized - closing_comm
            if after == 0 or (after > 0) != (before > 0):
                self.trades.append(
                    Trade(fill.symbol, trade.side, trade.entry_time, fill.timestamp, trade.pnl)
                )
                del self._open[fill.symbol]
                trade = None

        if after != 0:
            if trade is None:
                trade = _OpenTrade(side="LONG" if after > 0 else "SHORT", entry_time=fill.timestamp)
                self._open[fill.symbol] = trade
            trade.pnl -= opening_comm

    @property
    def open_trades(self) -> int:
        return len(self._open)
