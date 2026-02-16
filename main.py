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
    if args.no_db:
        config.setdefault("persistence", {})["enabled"] = False
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Event-Driven Trading System")
    parser.add_argument("--config", type=Path, default=_DEFAULT_CONFIG,
                        help="Path to YAML config file")
    parser.add_argument("--symbol", type=str, default=None,
                        help="Override ticker symbol")
    parser.add_argument("--ticks", type=int, default=None,
                        help="Override number of ticks to simulate")
    parser.add_argument("--seed", type=int, default=None,
                        help="Override random seed")
    parser.add_argument("--no-db", action="store_true",
                        help="Disable SQLite persistence")
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()
    config = load_config(args.config)
    config = apply_overrides(config, args)

    report = BacktestEngine(config).run()
    print(report)


if __name__ == "__main__":
    main()
