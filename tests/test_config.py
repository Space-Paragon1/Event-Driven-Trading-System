"""Tests for BacktestConfig parsing and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from trading.config import BacktestConfig
from trading.errors import ConfigError

DEFAULT_YAML = Path(__file__).resolve().parents[1] / "config" / "default.yaml"


def test_shipped_default_yaml_matches_builtin_defaults() -> None:
    """config/default.yaml documents the defaults; keep the two in sync."""
    assert BacktestConfig.from_yaml(DEFAULT_YAML) == BacktestConfig()


def test_empty_mapping_gives_defaults() -> None:
    assert BacktestConfig.from_dict({}) == BacktestConfig()
    assert BacktestConfig.from_dict(None) == BacktestConfig()


def test_partial_sections_keep_other_defaults() -> None:
    cfg = BacktestConfig.from_dict({"strategy": {"type": "rsi", "period": 10}})
    assert (cfg.strategy.type, cfg.strategy.period) == ("rsi", 10)
    assert cfg.strategy.overbought == 70.0
    assert cfg.risk == BacktestConfig().risk


def test_unknown_section_is_rejected_with_suggestion() -> None:
    with pytest.raises(ConfigError, match=r"'stratgy'.*did you mean 'strategy'"):
        BacktestConfig.from_dict({"stratgy": {}})


def test_unknown_key_is_rejected_with_suggestion() -> None:
    with pytest.raises(ConfigError, match=r"strategy\.fast_perod.*did you mean 'fast_period'"):
        BacktestConfig.from_dict({"strategy": {"fast_perod": 3}})


def test_key_in_wrong_section_is_rejected() -> None:
    with pytest.raises(ConfigError, match=r"unknown config key 'simulation\.slow_period'"):
        BacktestConfig.from_dict({"simulation": {"slow_period": 20}})


def test_renamed_key_gets_a_precise_hint() -> None:
    with pytest.raises(ConfigError, match=r"simulation\.n_ticks' was renamed to 'n_bars'"):
        BacktestConfig.from_dict({"simulation": {"n_ticks": 100}})


def test_unknown_strategy_is_rejected_not_silently_random() -> None:
    """Regression: an unknown strategy type used to fall back to the random strategy."""
    with pytest.raises(ConfigError, match=r"unknown strategy 'rsii'.*did you mean 'rsi'"):
        BacktestConfig.from_dict({"strategy": {"type": "rsii"}})


@pytest.mark.parametrize(
    ("data", "where"),
    [
        ({"simulation": {"n_bars": 0}}, "simulation.n_bars"),
        ({"simulation": {"data_source": "bloomberg"}}, "simulation.data_source"),
        ({"simulation": {"data_source": "csv"}}, "simulation.csv_path"),
        ({"strategy": {"fast_period": 30, "slow_period": 20}}, "strategy.fast_period"),
        ({"strategy": {"type": "rsi", "oversold": 80}}, "strategy.oversold"),
        ({"order_manager": {"quantity": -5}}, "order_manager.quantity"),
        ({"execution": {"slippage_bps": -1}}, "execution.slippage_bps"),
        ({"risk": {"max_drawdown_pct": 0}}, "risk.max_drawdown_pct"),
        ({"portfolio": {"starting_cash": 0}}, "portfolio.starting_cash"),
        ({"metrics": {"periods_per_year": 0}}, "metrics.periods_per_year"),
    ],
)
def test_invalid_values_report_their_location(data: dict[str, object], where: str) -> None:
    with pytest.raises(ConfigError, match=where.replace(".", r"\.")):
        BacktestConfig.from_dict(data)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "data",
    [
        {"order_manager": {"quantity": "100"}},
        {"order_manager": {"quantity": 1.5}},
        {"order_manager": {"allow_short": "yes"}},
        {"risk": {"max_position": True}},
        {"simulation": "AAPL"},
    ],
)
def test_wrong_types_are_rejected(data: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        BacktestConfig.from_dict(data)  # type: ignore[arg-type]


def test_ints_are_accepted_for_floats_and_dates_for_strings(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("simulation:\n  start: 2023-01-01\nexecution:\n  slippage_bps: 2\n")
    cfg = BacktestConfig.from_yaml(path)
    assert cfg.simulation.start == "2023-01-01"
    assert cfg.execution.slippage_bps == 2.0


def test_with_overrides_validates_and_ignores_none() -> None:
    cfg = BacktestConfig().with_overrides({"strategy.type": "rsi", "simulation.symbol": None})
    assert cfg.strategy.type == "rsi"
    assert cfg.simulation.symbol == "AAPL"
    with pytest.raises(ConfigError):
        BacktestConfig().with_overrides({"strategy.type": "nope"})
    with pytest.raises(ConfigError, match="invalid override"):
        BacktestConfig().with_overrides({"strategy": "rsi"})


def test_round_trip_through_dict() -> None:
    cfg = BacktestConfig().with_overrides({"risk.max_position": 42})
    assert BacktestConfig.from_dict(cfg.to_dict()) == cfg


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, 252),
        ({"simulation.data_source": "yfinance", "simulation.interval": "1wk"}, 52),
        ({"simulation.data_source": "yfinance", "simulation.interval": "1h"}, 252 * 7),
        ({"metrics.periods_per_year": 12.0}, 12),
    ],
)
def test_periods_per_year(overrides: dict[str, object], expected: float) -> None:
    assert BacktestConfig().with_overrides(overrides).periods_per_year == expected


def test_bad_yaml_and_missing_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("simulation: [unclosed\n")
    with pytest.raises(ConfigError, match="invalid YAML"):
        BacktestConfig.from_yaml(bad)
    with pytest.raises(ConfigError, match="cannot read"):
        BacktestConfig.from_yaml(tmp_path / "missing.yaml")
    top_level_list = tmp_path / "list.yaml"
    top_level_list.write_text("- 1\n")
    with pytest.raises(ConfigError, match="mapping"):
        BacktestConfig.from_yaml(top_level_list)
