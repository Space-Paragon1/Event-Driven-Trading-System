# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-11-17

This release fixes bugs that made 0.1.0 backtest results meaningless, so results from 0.1.0
are not comparable with this version.

### Fixed

- **Every order was priced off the final bar.** Feeds published all bars to the bus before
  it was drained, so every signal, order and fill was processed after the last bar. All
  fills happened at roughly the final close, and P&L was essentially commissions. The
  engine now drives the bus one bar at a time.
- **Look-ahead bias.** Orders filled at the close of the bar that generated them. They now
  fill at the next bar's open.
- **Short-position accounting.** Selling from flat booked the full sale notional as realized
  P&L with an average cost of 0. Position accounting now handles longs, shorts, partial
  closes and flips.
- **Metrics on a trade-sampled curve.** Equity was recorded only on fills, which hid drawdowns
  between trades, and Sharpe was annualised with √252 regardless of bar size. Equity is now
  marked to market every bar, and annualisation follows the data interval.
- **Win rate counted fills, not trades.** A buy above the previous average cost counted as a
  "win". Win rate, profit factor and average P&L now use closed round trips, net of
  commission.
- **Exposure stacking.** Every BUY signal added another fixed-size lot, without limit. Orders
  are now sized to a target position, net of working orders.
- **Risk checks used stale positions**, and the drawdown check blocked orders that would
  reduce risk. Both are fixed.
- **Unknown strategy names silently ran the random strategy.** They now raise a config error
  with a suggestion.
- **The package could not be installed** (invalid build backend). `pip install .` now works.

### Added

- `trading-backtest` console script, `python -m trading`, and `--json`, `--csv`, `--source`,
  `--quantity`, `--allow-short`, `--db`, `-v`/`-q` and `--version` flags.
- Typed, validated configuration (`BacktestConfig`) with "did you mean" hints for unknown
  keys.
- `Strategy` base class, strategy registry, and incremental `SMA` / Wilder `RSI` indicators.
- Long/short support (`order_manager.allow_short`).
- Metrics: CAGR, volatility, Sortino, Calmar, drawdown duration, profit factor, exposure,
  buy-and-hold benchmark, total commission, configurable risk-free rate.
- `BacktestResult` with the equity curve, prices, fills and trades for programmatic use.
- A three-panel chart (price with fills, equity vs. benchmark, drawdown) that renders
  headless.
- CSV data source wired into config and the CLI, with column, date-order and value
  validation.
- SQLite `runs` table and per-row `run_id`, a single-transaction write with rollback on
  error, and schema versioning.
- Optional dependency extras: `[data]` (yfinance), `[viz]` (matplotlib), `[all]`, `[dev]`.
- Strict mypy, ruff, pre-commit hooks, a Makefile and GitHub Actions CI (Linux, macOS and
  Windows; Python 3.11–3.14).
- 220+ tests, including end-to-end causality and accounting invariants, property-based
  tests, and a regression test for each fix above.

### Changed

- The synthetic feed now generates daily business-day bars from a geometric Brownian motion
  (`n_bars`, `annual_drift`, `annual_volatility`). It previously produced a minute-bar
  random walk.
- Slippage is adverse (buys pay more, sells receive less) instead of symmetric random noise.
- Order and fill IDs are sequential (`O000001`, `F000001`), so runs are reproducible.
- Per-bar log lines moved to DEBUG, and logs now go to stderr.
- `simulation.n_ticks` was renamed to `simulation.n_bars`. `--ticks` still works as an alias
  for `--bars`.
- `SignalGenerator` was renamed to `RandomStrategy`, and `MarketDataFeed` to `SyntheticFeed`.

### Removed

- `requirements.txt`. Dependencies live in `pyproject.toml` only.
- Generated artifacts (`trading.db`, chart PNGs) are no longer committed.

## [0.1.0]

- Initial event-driven pipeline: event bus, synthetic, CSV and Yahoo Finance feeds,
  MA-crossover, RSI and random strategies, order manager, risk manager, execution
  simulator, portfolio tracker, metrics, SQLite persistence and an equity chart.

[0.2.0]: https://github.com/Space-Paragon1/Event-Driven-Trading-System/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Space-Paragon1/Event-Driven-Trading-System/releases/tag/v0.1.0
