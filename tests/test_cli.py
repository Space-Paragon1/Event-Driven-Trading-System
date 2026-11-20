"""Tests for the command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading import __version__
from trading.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, main


def test_default_run_prints_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--no-db", "--bars", "60", "-q"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "PERFORMANCE REPORT" in out
    assert "ma_crossover" in out


def test_json_output_is_clean_and_parseable(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--no-db", "--bars", "60", "--strategy", "rsi", "--json"]) == EXIT_OK
    out, err = capsys.readouterr()
    data = json.loads(out)  # logs go to stderr, so stdout is pure JSON
    assert data["strategy"] == "rsi"
    assert data["metrics"]["n_bars"] == 60
    assert "[" not in out.splitlines()[0]
    assert err is not None


def test_ticks_alias_still_works(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--no-db", "--ticks", "40", "--json", "-q"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["metrics"]["n_bars"] == 40


def test_config_file_and_overrides(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text("simulation:\n  symbol: MSFT\n  n_bars: 50\nstrategy:\n  type: random\n")
    assert main(["--config", str(cfg), "--no-db", "--json", "--symbol", "NVDA", "-q"]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert (data["symbol"], data["strategy"], data["metrics"]["n_bars"]) == ("NVDA", "random", 50)


def test_csv_flag_implies_csv_source(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "p.csv"
    path.write_text("date,open,high,low,close,volume\n2024-01-02,1,1,1,1,1\n2024-01-03,1,1,1,1,1\n")
    assert main(["--csv", str(path), "--no-db", "--json", "-q"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["data_source"] == "csv"


def test_db_path_flag(tmp_path: Path) -> None:
    db = tmp_path / "out.db"
    assert main(["--bars", "30", "--db", str(db), "-q"]) == EXIT_OK
    assert db.exists()


def test_save_chart(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    out = tmp_path / "chart.png"
    assert main(["--no-db", "--bars", "60", "--save-chart", str(out), "-q"]) == EXIT_OK
    assert out.stat().st_size > 10_000


def test_config_error_exits_with_usage_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text("strategy:\n  type: momentum\n")
    assert main(["--config", str(cfg)]) == EXIT_USAGE
    assert "unknown strategy 'momentum'" in capsys.readouterr().err


def test_data_error_exits_with_failure_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--csv", str(tmp_path / "missing.csv"), "--no-db"]) == EXIT_FAILURE
    assert "cannot open" in capsys.readouterr().err


def test_invalid_choice_is_rejected_by_argparse() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--strategy", "nope"])
    assert exc.value.code == EXIT_USAGE


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--version"])
    assert __version__ in capsys.readouterr().out
