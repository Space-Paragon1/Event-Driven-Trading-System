"""Tests for BacktestEngine."""

from __future__ import annotations

from trading.backtest.engine import BacktestEngine, BacktestReport
from trading.metrics.calculator import PerformanceReport

_BASE_CONFIG = {
    "simulation": {"symbol": "AAPL", "n_ticks": 50, "seed": 99},
    "strategy": {"type": "ma_crossover", "fast_period": 5, "slow_period": 20},
    "order_manager": {"quantity": 100},
    "execution": {"slippage_bps": 1, "commission_per_share": 0.01},
    "risk": {"max_position": 500, "max_drawdown_pct": 10.0},
    "portfolio": {"starting_cash": 100_000.0},
    "persistence": {"enabled": False},
}


def _run(extra: dict | None = None, enable_db: bool = False) -> BacktestReport:
    config = {**_BASE_CONFIG}
    if extra:
        for k, v in extra.items():
            config.setdefault(k, {}).update(v)
    return BacktestEngine(config, enable_db=enable_db).run()


def test_report_is_returned() -> None:
    report = _run()
    assert isinstance(report, BacktestReport)
    assert isinstance(report.performance, PerformanceReport)


def test_report_symbol_correct() -> None:
    report = _run()
    assert report.symbol == "AAPL"


def test_report_n_ticks_correct() -> None:
    report = _run()
    assert report.n_ticks == 50


def test_final_equity_is_positive() -> None:
    report = _run()
    assert report.performance.final_equity > 0


def test_random_strategy_variant() -> None:
    report = _run(extra={"strategy": {"type": "random"}})
    assert isinstance(report, BacktestReport)


def test_str_representation() -> None:
    report = _run()
    text = str(report)
    assert "AAPL" in text
    assert "PERFORMANCE REPORT" in text


def test_engine_no_db_does_not_create_file(tmp_path) -> None:
    config = {**_BASE_CONFIG, "persistence": {"enabled": False, "db_path": str(tmp_path / "test.db")}}
    BacktestEngine(config, enable_db=False).run()
    assert not (tmp_path / "test.db").exists()
