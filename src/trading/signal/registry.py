"""Strategy registry — the single source of truth for strategy names."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from trading.signal.base import Strategy
from trading.signal.ma_crossover import MACrossoverStrategy
from trading.signal.random_strategy import RandomStrategy
from trading.signal.rsi import RSIStrategy

if TYPE_CHECKING:
    from trading.config import StrategyConfig

StrategyFactory = Callable[["StrategyConfig", "int | None"], Strategy]

STRATEGIES: dict[str, StrategyFactory] = {
    "ma_crossover": lambda cfg, _seed: MACrossoverStrategy(cfg.fast_period, cfg.slow_period),
    "rsi": lambda cfg, _seed: RSIStrategy(cfg.period, cfg.overbought, cfg.oversold),
    "random": lambda _cfg, seed: RandomStrategy(seed),
}


def build_strategy(cfg: StrategyConfig, seed: int | None = None) -> Strategy:
    """Instantiate the strategy named by ``cfg.type``."""
    try:
        factory = STRATEGIES[cfg.type]
    except KeyError:
        known = ", ".join(sorted(STRATEGIES))
        raise ValueError(f"unknown strategy {cfg.type!r} (expected one of: {known})") from None
    return factory(cfg, seed)
