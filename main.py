"""Entry point — loads config, applies CLI overrides, and runs the backtest."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from trading.backtest.engine import BacktestEngine

_DEFAULT_CONFIG = Path(__file__).parent / "config" / "default.yaml"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def load_config(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def apply_overrides(config: dict, args: argparse.Namespace) -> dict:
    sim = config.setdefault("simulation", {})
    if args.symbol:
        sim["symbol"] = args.symbol
    if args.ticks is not None:
        sim["n_ticks"] = args.ticks
    if args.seed is not None:
        sim["seed"] = args.seed
    if args.strategy:
        config.setdefault("strategy", {})["type"] = args.strategy
    if args.no_db:
        config.setdefault("persistence", {})["enabled"] = False
    # yfinance date range — also switches data_source
    if args.from_date or args.to_date:
        sim["data_source"] = "yfinance"
        if args.from_date:
            sim["start"] = args.from_date
        if args.to_date:
            sim["end"] = args.to_date
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Event-Driven Trading System")
    parser.add_argument("--config", type=Path, default=_DEFAULT_CONFIG,
                        help="Path to YAML config file")
    parser.add_argument("--symbol", type=str, default=None,
                        help="Override ticker symbol")
    parser.add_argument("--ticks", type=int, default=None,
                        help="Override number of ticks (synthetic feed only)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Override random seed")
    parser.add_argument("--strategy", type=str, default=None,
                        choices=["ma_crossover", "rsi", "random"],
                        help="Override strategy type")
    parser.add_argument("--no-db", action="store_true",
                        help="Disable SQLite persistence")
    parser.add_argument("--from", dest="from_date", type=str, default=None,
                        metavar="YYYY-MM-DD",
                        help="Start date for yfinance feed (implies --data-source yfinance)")
    parser.add_argument("--to", dest="to_date", type=str, default=None,
                        metavar="YYYY-MM-DD",
                        help="End date for yfinance feed")
    parser.add_argument("--chart", action="store_true",
                        help="Show equity curve chart after backtest")
    parser.add_argument("--save-chart", dest="save_chart", type=str, default=None,
                        metavar="PATH",
                        help="Save equity chart to file instead of displaying")
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()
    config = load_config(args.config)
    config = apply_overrides(config, args)

    enable_chart = args.chart or bool(args.save_chart)
    report = BacktestEngine(
        config,
        enable_chart=enable_chart if enable_chart else None,
        chart_save_path=args.save_chart,
    ).run()
    print(report)


if __name__ == "__main__":
    main()
