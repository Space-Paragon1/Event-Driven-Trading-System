"""Typed event dataclasses for the trading pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto


class Direction(Enum):
    BUY = auto()
    SELL = auto()
    HOLD = auto()


class OrderType(Enum):
    MARKET = auto()
    LIMIT = auto()


@dataclass(frozen=True)
class MarketDataEvent:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class SignalEvent:
    symbol: str
    timestamp: datetime
    direction: Direction
    strength: float  # 0.0 – 1.0


@dataclass(frozen=True)
class OrderEvent:
    order_id: str
    symbol: str
    timestamp: datetime
    order_type: OrderType
    direction: Direction
    quantity: int
    price: float  # 0.0 for MARKET orders


@dataclass(frozen=True)
class FillEvent:
    fill_id: str
    order_id: str
    symbol: str
    timestamp: datetime
    direction: Direction
    quantity: int
    fill_price: float
    commission: float


@dataclass(frozen=True)
class ApprovedOrderEvent:
    """Emitted by RiskManager when an order passes all risk checks."""

    order_id: str
    symbol: str
    timestamp: datetime
    order_type: OrderType
    direction: Direction
    quantity: int
    price: float


@dataclass(frozen=True)
class RiskVetoEvent:
    """Emitted by RiskManager when an order is rejected."""

    order_id: str
    symbol: str
    timestamp: datetime
    reason: str


@dataclass(frozen=True)
class PortfolioUpdateEvent:
    """Emitted by PortfolioTracker after every fill."""

    symbol: str
    timestamp: datetime
    position: int        # signed shares held (positive = long)
    avg_cost: float      # average cost basis per share
    realized_pnl: float
    unrealized_pnl: float
    cash: float
    equity: float        # cash + market value of all open positions
