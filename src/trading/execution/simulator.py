"""Execution simulator — fills approved orders with slippage and commission."""

from __future__ import annotations

import random
import uuid

from trading.bus.event_bus import EventBus
from trading.events.types import ApprovedOrderEvent, FillEvent

_SLIPPAGE_BPS = 1             # 1 basis point = 0.01 %
_COMMISSION_PER_SHARE = 0.01  # $0.01 per share


class ExecutionSimulator:
    """Subscribes to :class:`~trading.events.types.ApprovedOrderEvent` (orders
    that have passed the risk manager) and emits a
    :class:`~trading.events.types.FillEvent` simulating an immediate fill.

    The reference price is taken from ``event.price`` if non-zero; otherwise
    falls back to ``$150`` (useful in tests that don't wire an OrderManager).

    Slippage is applied as ±*slippage_bps* basis points drawn uniformly.

    Args:
        slippage_bps:          One-sided slippage in basis points.
        commission_per_share:  Commission charged per share.
        seed:                  Optional RNG seed.
    """

    def __init__(
        self,
        slippage_bps: float = _SLIPPAGE_BPS,
        commission_per_share: float = _COMMISSION_PER_SHARE,
        seed: int | None = None,
    ) -> None:
        self.slippage_bps = slippage_bps
        self.commission_per_share = commission_per_share
        self._bus: EventBus | None = None
        self._rng = random.Random(seed)

    def register(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe(ApprovedOrderEvent, self._on_order)

    # ------------------------------------------------------------------

    def _on_order(self, event: ApprovedOrderEvent) -> None:
        assert self._bus is not None, "register() must be called before emitting events"

        ref_price = event.price if event.price > 0.0 else 150.0
        slip = ref_price * (self.slippage_bps / 10_000) * self._rng.uniform(-1.0, 1.0)
        fill_price = round(ref_price + slip, 4)
        commission = round(event.quantity * self.commission_per_share, 4)

        self._bus.publish(
            FillEvent(
                fill_id=str(uuid.uuid4()),
                order_id=event.order_id,
                symbol=event.symbol,
                timestamp=event.timestamp,
                direction=event.direction,
                quantity=event.quantity,
                fill_price=fill_price,
                commission=commission,
            )
        )
