"""Event-driven backtesting engine.

Quick start::

    from trading import BacktestConfig, BacktestEngine

    result = BacktestEngine(BacktestConfig()).run()
    print(result.report)
"""

from __future__ import annotations

__version__ = "0.2.0"

from trading.backtest.engine import BacktestEngine, BacktestResult
from trading.config import BacktestConfig
from trading.signal.base import Signal, Strategy

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "Signal",
    "Strategy",
    "__version__",
]
