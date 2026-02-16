"""Event logger — subscribes to all event types and writes structured logs."""

from __future__ import annotations

import logging

from trading.bus.event_bus import EventBus
from trading.events.types import (
    ApprovedOrderEvent,
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    PortfolioUpdateEvent,
    RiskVetoEvent,
    SignalEvent,
)

logger = logging.getLogger("trading")


class EventLogger:
    """Subscribes to every event type and logs them at INFO level.

    Each log line is prefixed with the event class name so log output can
    easily be filtered or parsed downstream.
    """

    def register(self, bus: EventBus) -> None:
        bus.subscribe(MarketDataEvent, self._on_market_data)
        bus.subscribe(SignalEvent, self._on_signal)
        bus.subscribe(OrderEvent, self._on_order)
        bus.subscribe(ApprovedOrderEvent, self._on_approved_order)
        bus.subscribe(RiskVetoEvent, self._on_risk_veto)
        bus.subscribe(FillEvent, self._on_fill)
        bus.subscribe(PortfolioUpdateEvent, self._on_portfolio_update)

    # ------------------------------------------------------------------

    def _on_market_data(self, event: MarketDataEvent) -> None:
        logger.info(
            "[MarketData] %s @ %s  O=%.2f H=%.2f L=%.2f C=%.2f V=%d",
            event.symbol,
            event.timestamp.isoformat(timespec="seconds"),
            event.open,
            event.high,
            event.low,
            event.close,
            event.volume,
        )

    def _on_signal(self, event: SignalEvent) -> None:
        logger.info(
            "[Signal]     %s @ %s  dir=%s strength=%.4f",
            event.symbol,
            event.timestamp.isoformat(timespec="seconds"),
            event.direction.name,
            event.strength,
        )

    def _on_order(self, event: OrderEvent) -> None:
        logger.info(
            "[Order]      %s @ %s  id=%s dir=%s qty=%d price=%.2f",
            event.symbol,
            event.timestamp.isoformat(timespec="seconds"),
            event.order_id[:8],
            event.direction.name,
            event.quantity,
            event.price,
        )

    def _on_approved_order(self, event: ApprovedOrderEvent) -> None:
        logger.info(
            "[Approved]   %s @ %s  id=%s dir=%s qty=%d",
            event.symbol,
            event.timestamp.isoformat(timespec="seconds"),
            event.order_id[:8],
            event.direction.name,
            event.quantity,
        )

    def _on_risk_veto(self, event: RiskVetoEvent) -> None:
        logger.warning(
            "[RiskVeto]   %s @ %s  id=%s reason=%s",
            event.symbol,
            event.timestamp.isoformat(timespec="seconds"),
            event.order_id[:8],
            event.reason,
        )

    def _on_fill(self, event: FillEvent) -> None:
        logger.info(
            "[Fill]       %s @ %s  order=%s dir=%s qty=%d price=%.4f comm=%.2f",
            event.symbol,
            event.timestamp.isoformat(timespec="seconds"),
            event.order_id[:8],
            event.direction.name,
            event.quantity,
            event.fill_price,
            event.commission,
        )

    def _on_portfolio_update(self, event: PortfolioUpdateEvent) -> None:
        logger.info(
            "[Portfolio]  %s @ %s  pos=%d avg=%.2f rpnl=%.2f upnl=%.2f cash=%.2f equity=%.2f",
            event.symbol,
            event.timestamp.isoformat(timespec="seconds"),
            event.position,
            event.avg_cost,
            event.realized_pnl,
            event.unrealized_pnl,
            event.cash,
            event.equity,
        )
