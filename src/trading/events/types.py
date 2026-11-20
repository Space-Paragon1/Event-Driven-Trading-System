"""Typed, immutable event definitions for the trading pipeline.

Every component communicates exclusively through these events. They are frozen,
slotted, keyword-only dataclasses: cheap to create, impossible to mutate once
published, and robust to field reordering.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Direction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

    @property
    def sign(self) -> int:
        """``+1`` for BUY, ``-1`` for SELL, ``0`` for HOLD."""
        return _SIGNS[self]


_SIGNS = {Direction.BUY: 1, Direction.SELL: -1, Direction.HOLD: 0}


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """Base class for every event on the bus."""

    symbol: str
    timestamp: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketDataEvent(Event):
    """One OHLCV bar. ``timestamp`` is the bar's period start."""

    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True, slots=True, kw_only=True)
class SignalEvent(Event):
    """A strategy's view after seeing a bar."""

    direction: Direction
    strength: float  # in [0, 1]


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderEvent(Event):
    """An order emitted by the order manager, before risk checks."""

    order_id: str
    order_type: OrderType
    direction: Direction
    quantity: int
    price: float  # reference price (last close) for MARKET orders

    @property
    def signed_quantity(self) -> int:
        return self.quantity * self.direction.sign


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovedOrderEvent(Event):
    """An order that passed every risk check and may be sent to execution."""

    order_id: str
    order_type: OrderType
    direction: Direction
    quantity: int
    price: float

    @property
    def signed_quantity(self) -> int:
        return self.quantity * self.direction.sign


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskVetoEvent(Event):
    """An order the risk manager rejected."""

    order_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class FillEvent(Event):
    """A completed execution. ``timestamp`` is the bar the fill happened on."""

    fill_id: str
    order_id: str
    direction: Direction
    quantity: int
    fill_price: float
    commission: float

    @property
    def signed_quantity(self) -> int:
        return self.quantity * self.direction.sign


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioUpdateEvent(Event):
    """Mark-to-market portfolio snapshot, published once per bar."""

    position: int  # signed shares held (positive = long)
    avg_cost: float  # average entry price of the open position (0.0 when flat)
    realized_pnl: float  # cumulative, before commissions
    unrealized_pnl: float
    cash: float
    equity: float  # cash + market value of all open positions


@dataclass(frozen=True, slots=True, kw_only=True)
class EndOfBarEvent(Event):
    """Clock event published by the engine once a bar's event cascade has settled.

    Components that need a consistent end-of-bar view (e.g. the portfolio's
    mark-to-market snapshot) act on this rather than on the raw bar, so that
    they see every fill that happened during the bar.
    """
