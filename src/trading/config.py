"""Typed, validated configuration.

A :class:`BacktestConfig` is built from defaults, an optional YAML file, and
CLI overrides, in that order. Unknown keys and invalid values raise
:class:`~trading.errors.ConfigError` with a precise location
(``strategy.slow_period``) and, for typos, a suggestion.
"""

from __future__ import annotations

import dataclasses
import difflib
import types
from dataclasses import dataclass, field, fields
from datetime import date
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

import yaml

from trading.errors import ConfigError
from trading.signal.registry import STRATEGIES

DATA_SOURCES = ("synthetic", "csv", "yfinance")

# Bars per year for common yfinance intervals (US equities: 252 sessions x 6.5 h).
_PERIODS_PER_YEAR = {
    "1m": 252 * 390,
    "2m": 252 * 195,
    "5m": 252 * 78,
    "15m": 252 * 26,
    "30m": 252 * 13,
    "60m": 252 * 7,
    "90m": 252 * 5,
    "1h": 252 * 7,
    "1d": 252,
    "5d": 52,
    "1wk": 52,
    "1mo": 12,
    "3mo": 4,
}


@dataclass(frozen=True)
class SimulationConfig:
    symbol: str = "AAPL"
    data_source: str = "synthetic"
    seed: int | None = 42
    # synthetic
    n_bars: int = 252
    start_price: float = 150.0
    annual_drift: float = 0.08
    annual_volatility: float = 0.25
    # yfinance
    start: str = "2024-01-01"
    end: str = "2024-12-31"
    interval: str = "1d"
    # csv
    csv_path: str | None = None

    def __post_init__(self) -> None:
        _check(bool(self.symbol), "simulation.symbol", "must not be empty")
        _check(
            self.data_source in DATA_SOURCES,
            "simulation.data_source",
            f"must be one of {', '.join(DATA_SOURCES)} (got {self.data_source!r})",
        )
        _check(self.n_bars > 0, "simulation.n_bars", "must be positive")
        _check(self.start_price > 0, "simulation.start_price", "must be positive")
        _check(self.annual_volatility >= 0, "simulation.annual_volatility", "must be >= 0")
        _check(
            self.data_source != "csv" or bool(self.csv_path),
            "simulation.csv_path",
            "is required when data_source is 'csv'",
        )


@dataclass(frozen=True)
class StrategyConfig:
    type: str = "ma_crossover"
    # ma_crossover
    fast_period: int = 5
    slow_period: int = 20
    # rsi
    period: int = 14
    overbought: float = 70.0
    oversold: float = 30.0

    def __post_init__(self) -> None:
        if self.type not in STRATEGIES:
            raise ConfigError(
                f"strategy.type: unknown strategy {self.type!r}{_suggest(self.type, STRATEGIES)} "
                f"(available: {', '.join(sorted(STRATEGIES))})"
            )
        if self.type == "ma_crossover":
            _check(self.fast_period >= 1, "strategy.fast_period", "must be >= 1")
            _check(
                self.fast_period < self.slow_period,
                "strategy.fast_period",
                f"must be less than slow_period ({self.fast_period} >= {self.slow_period})",
            )
        if self.type == "rsi":
            _check(self.period >= 2, "strategy.period", "must be >= 2")
            _check(
                0 <= self.oversold < self.overbought <= 100,
                "strategy.oversold",
                f"need 0 <= oversold < overbought <= 100 (got {self.oversold}, {self.overbought})",
            )


@dataclass(frozen=True)
class OrderManagerConfig:
    quantity: int = 100
    allow_short: bool = False

    def __post_init__(self) -> None:
        _check(self.quantity > 0, "order_manager.quantity", "must be positive")


@dataclass(frozen=True)
class ExecutionConfig:
    slippage_bps: float = 1.0
    commission_per_share: float = 0.01

    def __post_init__(self) -> None:
        _check(self.slippage_bps >= 0, "execution.slippage_bps", "must be >= 0")
        _check(self.commission_per_share >= 0, "execution.commission_per_share", "must be >= 0")


@dataclass(frozen=True)
class RiskConfig:
    max_position: int = 500
    max_drawdown_pct: float = 10.0

    def __post_init__(self) -> None:
        _check(self.max_position > 0, "risk.max_position", "must be positive")
        _check(0 < self.max_drawdown_pct <= 100, "risk.max_drawdown_pct", "must be in (0, 100]")


@dataclass(frozen=True)
class PortfolioConfig:
    starting_cash: float = 100_000.0

    def __post_init__(self) -> None:
        _check(self.starting_cash > 0, "portfolio.starting_cash", "must be positive")


@dataclass(frozen=True)
class MetricsConfig:
    periods_per_year: float | None = None  # None = infer from the data source / interval
    risk_free_rate: float = 0.0

    def __post_init__(self) -> None:
        _check(
            self.periods_per_year is None or self.periods_per_year > 0,
            "metrics.periods_per_year",
            "must be positive",
        )


@dataclass(frozen=True)
class PersistenceConfig:
    enabled: bool = True
    db_path: str = "trading.db"


@dataclass(frozen=True)
class VisualizationConfig:
    enabled: bool = False
    save_path: str | None = "equity_curve.png"  # None = open an interactive window


@dataclass(frozen=True)
class BacktestConfig:
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    order_manager: OrderManagerConfig = field(default_factory=OrderManagerConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)

    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BacktestConfig:
        """Build a config from a nested mapping (e.g. parsed YAML), validating everything."""
        data = data or {}
        if not isinstance(data, dict):
            raise ConfigError(f"config must be a mapping, got {type(data).__name__}")
        sections = {f.name: f for f in fields(cls)}
        _reject_unknown(data, sections, prefix="")
        kwargs: dict[str, Any] = {}
        for name, value in data.items():
            section_cls = get_type_hints(cls)[name]
            kwargs[name] = _build_section(section_cls, value, name)
        return cls(**kwargs)

    @classmethod
    def from_yaml(cls, path: str | Path) -> BacktestConfig:
        path = Path(path)
        try:
            text = path.read_text()
        except OSError as exc:
            raise ConfigError(f"cannot read config file {path}: {exc.strerror}") from exc
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def with_overrides(self, overrides: dict[str, Any]) -> BacktestConfig:
        """Return a copy with dotted-key overrides applied, e.g. ``{"strategy.type": "rsi"}``.

        ``None`` values are ignored so callers can pass optional CLI arguments directly.
        """
        nested = self.to_dict()
        for dotted, value in overrides.items():
            if value is None:
                continue
            section, _, key = dotted.partition(".")
            if section not in nested or not key:
                raise ConfigError(f"invalid override key {dotted!r}")
            nested[section][key] = value
        return BacktestConfig.from_dict(nested)

    @property
    def periods_per_year(self) -> float:
        """Bars per year used to annualise metrics."""
        if self.metrics.periods_per_year is not None:
            return self.metrics.periods_per_year
        if self.simulation.data_source == "yfinance":
            return _PERIODS_PER_YEAR.get(self.simulation.interval, 252)
        return 252


# ----------------------------------------------------------------------
# helpers


def _check(ok: bool, where: str, message: str) -> None:
    if not ok:
        raise ConfigError(f"{where}: {message}")


def _suggest(name: str, options: Any) -> str:
    match = difflib.get_close_matches(name, list(options), n=1)
    return f" (did you mean {match[0]!r}?)" if match else ""


# Keys renamed since earlier versions, so old config files get a precise hint.
_RENAMED = {"simulation.n_ticks": "n_bars"}


def _reject_unknown(data: dict[str, Any], known: Any, prefix: str) -> None:
    for key in data:
        if key not in known:
            where = f"{prefix}{key}"
            if where in _RENAMED:
                raise ConfigError(f"config key {where!r} was renamed to {_RENAMED[where]!r}")
            raise ConfigError(f"unknown config key {where!r}{_suggest(str(key), known)}")


def _build_section(section_cls: type[Any], value: Any, name: str) -> Any:
    if value is None:
        return section_cls()
    if not isinstance(value, dict):
        raise ConfigError(f"{name}: expected a mapping, got {type(value).__name__}")
    hints = get_type_hints(section_cls)
    known = {f.name for f in fields(section_cls)}
    _reject_unknown(value, known, prefix=f"{name}.")
    kwargs = {key: _coerce(raw, hints[key], f"{name}.{key}") for key, raw in value.items()}
    return section_cls(**kwargs)


def _coerce(value: Any, annotation: Any, where: str) -> Any:
    """Validate *value* against a simple annotation (str/int/float/bool, optionally ``| None``)."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if value is None:
            return None
        annotation = args[0]

    if annotation is bool:
        if isinstance(value, bool):
            return value
    elif annotation is int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    elif annotation is float:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    elif annotation is str:
        if isinstance(value, str):
            return value
        if isinstance(value, date):  # YAML parses unquoted 2024-01-01 as a date
            return value.isoformat()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    else:  # pragma: no cover - guards against adding an unsupported field type
        raise TypeError(f"unsupported config annotation {annotation!r} for {where}")

    raise ConfigError(f"{where}: expected {annotation.__name__}, got {value!r}")
