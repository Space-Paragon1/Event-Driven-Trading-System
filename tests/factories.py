"""Event factories and bus helpers shared across the test suite."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from trading.bus.event_bus import EventBus
from trading.events.types import (
    ApprovedOrderEvent,
    Direction,
    EndOfBarEvent,
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    OrderType,
    PortfolioUpdateEvent,
    SignalEvent,
)

T0 = datetime(2024, 1, 2)


def ts(i: int = 0) -> datetime:
    return T0 + timedelta(days=i)


def bar(
    close: float,
    i: int = 0,
    *,
    open: float | None = None,
    high: float | None = None,
    low: float | None = None,
    symbol: str = "AAPL",
    volume: int = 1_000,
) -> MarketDataEvent:
    o = close if open is None else open
    return MarketDataEvent(
        symbol=symbol,
        timestamp=ts(i),
        open=o,
        high=max(o, close) if high is None else high,
        low=min(o, close) if low is None else low,
        close=close,
        volume=volume,
    )


def bars(closes: list[float], *, symbol: str = "AAPL") -> list[MarketDataEvent]:
    return [bar(c, i, symbol=symbol) for i, c in enumerate(closes)]


def signal(direction: Direction, i: int = 0, *, symbol: str = "AAPL") -> SignalEvent:
    return SignalEvent(symbol=symbol, timestamp=ts(i), direction=direction, strength=0.5)


def order(
    direction: Direction = Direction.BUY,
    qty: int = 100,
    *,
    order_id: str = "O1",
    price: float = 150.0,
    symbol: str = "AAPL",
    i: int = 0,
) -> OrderEvent:
    return OrderEvent(
        symbol=symbol,
        timestamp=ts(i),
        order_id=order_id,
        order_type=OrderType.MARKET,
        direction=direction,
        quantity=qty,
        price=price,
    )


def approved(
    direction: Direction = Direction.BUY,
    qty: int = 100,
    *,
    order_id: str = "O1",
    price: float = 150.0,
    symbol: str = "AAPL",
    order_type: OrderType = OrderType.MARKET,
    i: int = 0,
) -> ApprovedOrderEvent:
    return ApprovedOrderEvent(
        symbol=symbol,
        timestamp=ts(i),
        order_id=order_id,
        order_type=order_type,
        direction=direction,
        quantity=qty,
        price=price,
    )


def fill(
    direction: Direction,
    qty: int = 100,
    price: float = 150.0,
    commission: float = 0.0,
    *,
    i: int = 0,
    order_id: str = "O1",
    symbol: str = "AAPL",
) -> FillEvent:
    return FillEvent(
        symbol=symbol,
        timestamp=ts(i),
        fill_id=f"F-{order_id}",
        order_id=order_id,
        direction=direction,
        quantity=qty,
        fill_price=price,
        commission=commission,
    )


def snapshot(
    equity: float, i: int = 0, *, position: int = 0, symbol: str = "AAPL"
) -> PortfolioUpdateEvent:
    return PortfolioUpdateEvent(
        symbol=symbol,
        timestamp=ts(i),
        position=position,
        avg_cost=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        cash=equity,
        equity=equity,
    )


def end_of_bar(i: int = 0, *, symbol: str = "AAPL") -> EndOfBarEvent:
    return EndOfBarEvent(symbol=symbol, timestamp=ts(i))


class Capture:
    """Records every event of the given types published on a bus."""

    def __init__(self, bus: EventBus, *types: type) -> None:
        self.events: defaultdict[type, list[Any]] = defaultdict(list)
        for t in types:
            bus.subscribe(t, self.events[t].append)

    def __getitem__(self, t: type) -> list[Any]:
        return self.events[t]


def publish_all(bus: EventBus, *events: object) -> None:
    for e in events:
        bus.publish(e)
    bus.run()
