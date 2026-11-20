"""Command-line interface: ``trading-backtest`` / ``python -m trading``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from trading import __version__
from trading.backtest.engine import BacktestEngine, BacktestResult
from trading.config import DATA_SOURCES, BacktestConfig
from trading.errors import ConfigError, TradingError
from trading.signal.registry import STRATEGIES

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="trading-backtest",
        description="Run an event-driven backtest. Options override values from --config.",
        epilog=(
            "examples:\n"
            "  trading-backtest --strategy rsi --bars 500\n"
            "  trading-backtest --symbol MSFT --from 2022-01-01 --to 2024-12-31 \\\n"
            "                   --save-chart msft.png\n"
            "  trading-backtest --csv prices.csv --symbol SPY --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--config", type=Path, metavar="PATH", help="YAML config file")

    data = p.add_argument_group("data")
    data.add_argument("--symbol", help="ticker symbol")
    data.add_argument("--source", choices=DATA_SOURCES, help="market data source")
    data.add_argument("--bars", "--ticks", dest="bars", type=int, metavar="N",
                      help="number of synthetic bars")  # fmt: skip
    data.add_argument("--seed", type=int, help="random seed for synthetic data / random strategy")
    data.add_argument("--csv", dest="csv_path", metavar="PATH",
                      help="replay bars from a CSV file (implies --source csv)")  # fmt: skip
    data.add_argument("--from", dest="start", metavar="YYYY-MM-DD",
                      help="Yahoo Finance start date (implies --source yfinance)")  # fmt: skip
    data.add_argument("--to", dest="end", metavar="YYYY-MM-DD",
                      help="Yahoo Finance end date, exclusive (implies yfinance)")  # fmt: skip
    data.add_argument("--interval", help="Yahoo Finance bar interval, e.g. 1d, 1wk, 1h")

    trading = p.add_argument_group("trading")
    trading.add_argument("--strategy", choices=sorted(STRATEGIES), help="signal strategy")
    trading.add_argument("--quantity", type=int, metavar="N", help="target position size in shares")
    trading.add_argument("--allow-short", action="store_true", default=None,
                         help="let SELL signals open short positions")  # fmt: skip

    output = p.add_argument_group("output")
    output.add_argument("--db", dest="db_path", metavar="PATH", help="SQLite database path")
    output.add_argument("--no-db", action="store_true", help="disable SQLite persistence")
    output.add_argument("--chart", action="store_true", help="show the chart in a window")
    output.add_argument("--save-chart", metavar="PATH", help="save the chart (PNG/SVG/PDF)")
    output.add_argument("--json", action="store_true", help="print the result as JSON")
    verbosity = output.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="log every event")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="log warnings only")
    return p


def config_from_args(args: argparse.Namespace) -> BacktestConfig:
    """Load the config file (or defaults) and apply command-line overrides."""
    config = BacktestConfig.from_yaml(args.config) if args.config else BacktestConfig()

    source = args.source
    if source is None and args.csv_path:
        source = "csv"
    if source is None and (args.start or args.end):
        source = "yfinance"

    overrides: dict[str, Any] = {
        "simulation.symbol": args.symbol,
        "simulation.data_source": source,
        "simulation.n_bars": args.bars,
        "simulation.seed": args.seed,
        "simulation.csv_path": args.csv_path,
        "simulation.start": args.start,
        "simulation.end": args.end,
        "simulation.interval": args.interval,
        "strategy.type": args.strategy,
        "order_manager.quantity": args.quantity,
        "order_manager.allow_short": args.allow_short,
        "persistence.db_path": args.db_path,
    }
    if args.no_db:
        overrides["persistence.enabled"] = False
    return config.with_overrides(overrides)


def render_chart(result: BacktestResult, args: argparse.Namespace) -> None:
    from trading.visualization.chart import plot_backtest

    viz = result.config.visualization
    save_path = args.save_chart
    show = args.chart
    if not (save_path or show) and viz.enabled:
        save_path = viz.save_path
        show = viz.save_path is None
    if save_path or show:
        plot_backtest(result, save_path=save_path, show=show)
        if save_path:
            logging.getLogger("trading").info("Chart saved to %s", save_path)


def setup_logging(args: argparse.Namespace) -> None:
    level = logging.DEBUG if args.verbose else logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
        force=True,
    )
    # Third-party libraries stay quiet even with -v.
    for noisy in ("matplotlib", "PIL", "yfinance", "urllib3", "peewee"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args)

    try:
        config = config_from_args(args)
    except ConfigError as exc:
        parser.print_usage(sys.stderr)
        print(f"{parser.prog}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        result = BacktestEngine(config).run()
        render_chart(result, args)
    except TradingError as exc:
        print(f"{parser.prog}: error: {exc}", file=sys.stderr)
        return EXIT_FAILURE

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
