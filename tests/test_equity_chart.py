"""Tests for EquityChart."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be set before other matplotlib imports

from datetime import datetime, timedelta

from trading.bus.event_bus import EventBus
from trading.events.types import PortfolioUpdateEvent
from trading.visualization.chart import EquityChart

_BASE_TS = datetime(2024, 1, 2, 9, 30)

_EQUITY_VALUES = [100_000.0, 100_500.0, 99_800.0, 101_200.0, 102_000.0]


def _make_portfolio_event(equity: float, i: int = 0) -> PortfolioUpdateEvent:
    return PortfolioUpdateEvent(
        symbol="AAPL",
        timestamp=_BASE_TS + timedelta(days=i),
        position=100,
        avg_cost=150.0,
        realized_pnl=0.0,
        unrealized_pnl=equity - 100_000.0,
        cash=85_000.0,
        equity=equity,
    )


def _run_chart(equities: list[float]) -> EquityChart:
    bus = EventBus()
    chart = EquityChart()
    chart.register(bus)
    for i, eq in enumerate(equities):
        bus.publish(_make_portfolio_event(eq, i))
    bus.run()
    return chart


def test_plot_with_no_data_does_not_raise() -> None:
    chart = EquityChart()
    chart.plot()  # should print a warning and return cleanly


def test_correct_equity_point_count() -> None:
    chart = _run_chart(_EQUITY_VALUES)
    assert len(chart._equity) == len(_EQUITY_VALUES)


def test_equity_values_match_events() -> None:
    chart = _run_chart(_EQUITY_VALUES)
    assert chart._equity == _EQUITY_VALUES


def test_plot_saves_file(tmp_path) -> None:
    chart = _run_chart(_EQUITY_VALUES)
    out = tmp_path / "curve.png"
    chart.plot(symbol="AAPL", save_path=str(out))
    assert out.exists()
    assert out.stat().st_size > 0
