"""Tests for the backtest chart."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

from trading.backtest.engine import BacktestEngine, BacktestResult
from trading.config import BacktestConfig
from trading.visualization.chart import plot_backtest


@pytest.fixture(scope="module")
def result() -> BacktestResult:
    cfg = BacktestConfig().with_overrides({"persistence.enabled": False, "simulation.n_bars": 120})
    return BacktestEngine(cfg).run()


def test_returns_three_panel_figure(result: BacktestResult) -> None:
    fig = plot_backtest(result)
    assert len(fig.axes) == 3


@pytest.mark.parametrize("suffix", [".png", ".svg"])
def test_saves_file(result: BacktestResult, tmp_path: Path, suffix: str) -> None:
    out = tmp_path / f"chart{suffix}"
    plot_backtest(result, save_path=out)
    assert out.stat().st_size > 0


def test_marks_every_fill(result: BacktestResult) -> None:
    fig = plot_backtest(result)
    price_ax = fig.axes[0]
    plotted = sum(len(c.get_offsets()) for c in price_ax.collections)
    assert plotted == len(result.fills)
