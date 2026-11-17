"""Event logger — structured log lines for every event type.

Trading activity (BUY/SELL signals, orders, approvals, vetoes, fills) logs at
INFO. Per-bar noise (market data, HOLD signals, portfolio snapshots) logs at
DEBUG, so a multi-year run stays readable by default and fully traceable with
``-v``.
"""

from __future__ import annotations

import logging

from trading.bus.event_bus import EventBus
from trading.events.types import (
    ApprovedOrderEvent,
    Direction,
    Event,
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    PortfolioUpdateEvent,
    RiskVetoEvent,
    SignalEvent,
)

logger = logging.getLogger("trading.events")


def _ts(event: Event) -> str:
    return event.timestamp.isoformat(sep=" ", timespec="minutes")


class EventLogger:
    """Subscribes to every event type and logs it via the ``trading.events`` logger."""

    def register(self, bus: EventBus) -> None:
        bus.subscribe(MarketDataEvent, self._on_market_data)
        bus.subscribe(SignalEvent, self._on_signal)
        bus.subscribe(OrderEvent, self._on_order)
        bus.subscribe(ApprovedOrderEvent, self._on_approved_order)
        bus.subscribe(RiskVetoEvent, self._on_risk_veto)
        bus.subscribe(FillEvent, self._on_fill)
        bus.subscribe(PortfolioUpdateEvent, self._on_portfolio_update)

    # ------------------------------------------------------------------

    def _on_market_data(self, e: MarketDataEvent) -> None:
        logger.debug(
            "[MarketData] %s %s  O=%.2f H=%.2f L=%.2f C=%.2f V=%d",
            e.symbol, _ts(e), e.open, e.high, e.low, e.close, e.volume,
        )  # fmt: skip

    def _on_signal(self, e: SignalEvent) -> None:
        level = logging.DEBUG if e.direction is Direction.HOLD else logging.INFO
        logger.log(
            level, "[Signal]     %s %s  %s strength=%.4f",
            e.symbol, _ts(e), e.direction.name, e.strength,
        )  # fmt: skip

    def _on_order(self, e: OrderEvent) -> None:
        logger.info(
            "[Order]      %s %s  %s %s %d @ ref %.2f",
            e.symbol, _ts(e), e.order_id, e.direction.name, e.quantity, e.price,
        )  # fmt: skip

    def _on_approved_order(self, e: ApprovedOrderEvent) -> None:
        logger.info("[Approved]   %s %s  %s", e.symbol, _ts(e), e.order_id)

    def _on_risk_veto(self, e: RiskVetoEvent) -> None:
        logger.warning("[RiskVeto]   %s %s  %s  %s", e.symbol, _ts(e), e.order_id, e.reason)

    def _on_fill(self, e: FillEvent) -> None:
        logger.info(
            "[Fill]       %s %s  %s %s %d @ %.4f  comm=%.2f",
            e.symbol, _ts(e), e.order_id, e.direction.name, e.quantity, e.fill_price, e.commission,
        )  # fmt: skip

    def _on_portfolio_update(self, e: PortfolioUpdateEvent) -> None:
        logger.debug(
            "[Portfolio]  %s %s  pos=%d avg=%.2f rpnl=%.2f upnl=%.2f cash=%.2f equity=%.2f",
            e.symbol, _ts(e), e.position, e.avg_cost, e.realized_pnl, e.unrealized_pnl,
            e.cash, e.equity,
        )  # fmt: skip
