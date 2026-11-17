"""Backtest chart: price with executions, equity vs. buy-and-hold, and drawdown."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from trading.errors import MissingDependencyError
from trading.events.types import Direction
from trading.metrics.stats import drawdown_series

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from trading.backtest.engine import BacktestResult

_BLUE = "#2563eb"
_GREY = "#94a3b8"
_GREEN = "#16a34a"
_RED = "#dc2626"
_INK = "#0f172a"


def plot_backtest(
    result: BacktestResult,
    save_path: str | Path | None = None,
    *,
    show: bool = False,
) -> Figure:
    """Render a three-panel chart of *result*.

    - **Price** with BUY (▲) and SELL (▼) fills marked where they executed.
    - **Equity** against a buy-and-hold benchmark scaled to the same capital.
    - **Drawdown** from the running equity peak.

    Args:
        result:    Output of :meth:`BacktestEngine.run`.
        save_path: Write the figure here (format from the extension: PNG, SVG, PDF …).
        show:      Open an interactive window (requires a GUI backend).

    Returns:
        The matplotlib :class:`~matplotlib.figure.Figure`.
    """
    try:
        import matplotlib.dates as mdates
        from matplotlib.figure import Figure
        from matplotlib.ticker import FuncFormatter
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise MissingDependencyError("matplotlib", "viz") from exc

    if not result.equity_curve:
        raise ValueError("result has no equity data to plot")

    if show:
        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=(12, 8.5))
    else:
        fig = Figure(figsize=(12, 8.5))  # no pyplot: safe headless and in threads

    axes = fig.subplots(3, 1, sharex=True, gridspec_kw={"height_ratios": [2.2, 2.2, 1]})
    ax_px, ax_eq, ax_dd = axes
    fig.subplots_adjust(hspace=0.06, left=0.08, right=0.97, top=0.9, bottom=0.07)

    # --- Price + executions ---------------------------------------------------
    px_t = [t for t, _ in result.prices]
    px = [p for _, p in result.prices]
    ax_px.plot(px_t, px, color=_INK, linewidth=1.1, label=f"{result.symbol} close")
    for direction, marker, color in ((Direction.BUY, "^", _GREEN), (Direction.SELL, "v", _RED)):
        fills = [f for f in result.fills if f.direction is direction]
        ax_px.scatter(
            [f.timestamp for f in fills],
            [f.fill_price for f in fills],
            marker=marker,
            s=46,
            color=color,
            edgecolors="white",
            linewidths=0.6,
            zorder=3,
            label=f"{direction.name.title()} fill",
        )
    ax_px.set_ylabel("Price")
    ax_px.legend(loc="best", fontsize=9, framealpha=0.9, edgecolor="none", ncol=3)

    # --- Equity vs benchmark -------------------------------------------------
    eq_t = [t for t, _ in result.equity_curve]
    eq = [e for _, e in result.equity_curve]
    start = result.report.starting_equity
    benchmark = [start * p / px[0] for p in px] if px and px[0] else []
    ax_eq.plot(eq_t, eq, color=_BLUE, linewidth=1.6, label="Strategy")
    if benchmark:
        ax_eq.plot(px_t, benchmark, color=_GREY, linewidth=1.1, label="Buy & hold")
    ax_eq.axhline(start, color=_GREY, linestyle=":", linewidth=0.8)
    ax_eq.fill_between(eq_t, eq, start, where=[e >= start for e in eq], color=_GREEN, alpha=0.08)
    ax_eq.fill_between(eq_t, eq, start, where=[e < start for e in eq], color=_RED, alpha=0.10)
    ax_eq.set_ylabel("Equity")
    ax_eq.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax_eq.legend(loc="best", fontsize=9, framealpha=0.9, edgecolor="none", ncol=2)

    # --- Drawdown --------------------------------------------------------------
    dd = [-100.0 * d for d in drawdown_series([start, *eq])[1:]]
    ax_dd.fill_between(eq_t, dd, 0, color=_RED, alpha=0.35, linewidth=0)
    ax_dd.plot(eq_t, dd, color=_RED, linewidth=0.8)
    ax_dd.set_ylabel("Drawdown")
    ax_dd.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))

    for ax in axes:
        ax.grid(True, color="#e2e8f0", linewidth=0.7)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    locator = mdates.AutoDateLocator()  # type: ignore[no-untyped-call]
    ax_dd.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))  # type: ignore[no-untyped-call]

    r = result.report
    fig.suptitle(
        f"{result.symbol} · {result.strategy}",
        x=0.08,
        y=0.975,
        ha="left",
        fontsize=14,
        fontweight="bold",
        color=_INK,
    )
    fig.text(
        0.08,
        0.935,
        f"Return {r.total_return_pct:+.1f}%  (buy & hold {r.benchmark_return_pct:+.1f}%)   "
        f"Sharpe {r.sharpe_ratio:.2f}   Max DD {r.max_drawdown_pct:.1f}%   "
        f"Round trips {r.total_trades}   Win rate {r.win_rate_pct:.0f}%",
        fontsize=10,
        color="#475569",
    )

    if save_path is not None:
        fig.savefig(save_path, dpi=150)
    if show:
        import matplotlib.pyplot as plt

        plt.show()
    return fig
