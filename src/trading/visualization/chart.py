"""Equity curve visualization — plots equity and drawdown after a backtest run."""

from __future__ import annotations

from datetime import datetime

from trading.bus.event_bus import EventBus
from trading.events.types import PortfolioUpdateEvent


class EquityChart:
    """Collects portfolio snapshots during a backtest and produces a two-panel chart:

    - **Top panel** — equity curve with a dashed baseline and green/red fill
      above/below the starting equity level.
    - **Bottom panel** — running drawdown percentage (filled red area).

    Usage::

        chart = EquityChart()
        chart.register(bus)
        feed.emit(bus)
        bus.run()
        chart.plot(symbol="AAPL")                   # interactive window
        chart.plot(symbol="AAPL", save_path="out.png")  # save to file

    The chart component must be registered **before** ``bus.run()`` so it
    receives all :class:`~trading.events.types.PortfolioUpdateEvent` events.
    """

    def __init__(self) -> None:
        self._timestamps: list[datetime] = []
        self._equity: list[float] = []

    # ------------------------------------------------------------------

    def register(self, bus: EventBus) -> None:
        bus.subscribe(PortfolioUpdateEvent, self._on_portfolio_update)

    def _on_portfolio_update(self, event: PortfolioUpdateEvent) -> None:
        self._timestamps.append(event.timestamp)
        self._equity.append(event.equity)

    # ------------------------------------------------------------------

    def plot(self, symbol: str = "", save_path: str | None = None) -> None:
        """Render the equity curve and drawdown chart.

        Args:
            symbol:    Ticker label shown in the chart title.
            save_path: If provided, save the figure to this path (PNG/PDF/SVG)
                       instead of displaying an interactive window.
        """
        if not self._equity:
            print("[EquityChart] No data to plot — run the backtest first.")
            return

        import matplotlib.pyplot as plt

        equity = self._equity
        timestamps = self._timestamps
        baseline = equity[0]

        # Compute running drawdown
        peak = equity[0]
        drawdown: list[float] = []
        for e in equity:
            if e > peak:
                peak = e
            dd = (peak - e) / peak * 100.0 if peak > 0 else 0.0
            drawdown.append(dd)

        fig, (ax_eq, ax_dd) = plt.subplots(
            2, 1,
            figsize=(12, 7),
            gridspec_kw={"height_ratios": [3, 1]},
            sharex=True,
        )
        fig.subplots_adjust(hspace=0.05)

        # --- Equity panel ---
        ax_eq.plot(timestamps, equity, color="#1f77b4", linewidth=1.5, label="Equity")
        ax_eq.axhline(baseline, color="grey", linestyle="--", linewidth=0.8, label="Baseline")
        ax_eq.fill_between(
            timestamps, equity, baseline,
            where=[e >= baseline for e in equity],
            color="green", alpha=0.12,
        )
        ax_eq.fill_between(
            timestamps, equity, baseline,
            where=[e < baseline for e in equity],
            color="red", alpha=0.18,
        )
        title = f"Equity Curve{' — ' + symbol if symbol else ''}"
        ax_eq.set_title(title, fontsize=13)
        ax_eq.set_ylabel("Equity ($)")
        ax_eq.legend(loc="upper left", fontsize=9)
        ax_eq.grid(True, alpha=0.3)
        ax_eq.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"${x:,.0f}")
        )

        # --- Drawdown panel ---
        ax_dd.fill_between(timestamps, drawdown, 0, color="red", alpha=0.4)
        ax_dd.set_ylabel("Drawdown (%)")
        ax_dd.set_xlabel("Date")
        ax_dd.invert_yaxis()
        ax_dd.grid(True, alpha=0.3)

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"[EquityChart] Chart saved to {save_path}")
            plt.close(fig)
        else:
            plt.show()
