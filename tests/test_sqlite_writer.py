"""Tests for SQLiteWriter."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from tests.factories import approved, bar, fill, order, publish_all, signal, snapshot, ts
from trading.bus.event_bus import EventBus
from trading.errors import DataError
from trading.events.types import Direction, RiskVetoEvent
from trading.persistence.sqlite_writer import SCHEMA_VERSION, SQLiteWriter

TABLES = (
    "runs", "market_data", "signals", "orders", "approved_orders",
    "risk_vetos", "fills", "portfolio_updates",
)  # fmt: skip


def _count(path: Path, table: str, run_id: str | None = None) -> int:
    with closing(sqlite3.connect(path)) as conn:
        if run_id is None:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        sql = f"SELECT COUNT(*) FROM {table} WHERE run_id = ?"
        return int(conn.execute(sql, (run_id,)).fetchone()[0])


def _write_run(path: Path, run_id: str) -> None:
    bus = EventBus()
    with SQLiteWriter(str(path), run_id) as db:
        db.start_run(symbol="AAPL", strategy="test", config={"k": 1})
        db.register(bus)
        publish_all(
            bus,
            bar(150.0),
            signal(Direction.BUY),
            order(),
            approved(),
            RiskVetoEvent(symbol="AAPL", timestamp=ts(), order_id="O2", reason="limit"),
            fill(Direction.BUY),
            snapshot(100_000.0),
        )
        db.finish_run({"total_return_pct": 1.5})


def test_schema_is_created_and_versioned(tmp_path: Path) -> None:
    path = tmp_path / "t.db"
    SQLiteWriter(str(path), "r1").close()
    with closing(sqlite3.connect(path)) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert set(TABLES) <= names
    assert version == SCHEMA_VERSION


def test_every_event_type_is_persisted_with_run_id(tmp_path: Path) -> None:
    path = tmp_path / "t.db"
    _write_run(path, "run-a")
    for table in TABLES:
        assert _count(path, table, "run-a") == 1, table


def test_runs_are_kept_separate(tmp_path: Path) -> None:
    path = tmp_path / "t.db"
    _write_run(path, "run-a")
    _write_run(path, "run-b")
    assert _count(path, "fills") == 2
    assert _count(path, "fills", "run-b") == 1


def test_run_row_has_config_and_report(tmp_path: Path) -> None:
    path = tmp_path / "t.db"
    _write_run(path, "run-a")
    with closing(sqlite3.connect(path)) as conn:
        cfg, rep, finished = conn.execute(
            "SELECT config_json, report_json, finished_at FROM runs WHERE run_id = 'run-a'"
        ).fetchone()
    assert json.loads(cfg) == {"k": 1}
    assert json.loads(rep) == {"total_return_pct": 1.5}
    assert finished is not None


def test_exception_rolls_back_the_run(tmp_path: Path) -> None:
    path = tmp_path / "t.db"

    def crashing_run() -> None:
        bus = EventBus()
        with SQLiteWriter(str(path), "boom") as db:
            db.start_run(symbol="AAPL", strategy="test", config={})
            db.register(bus)
            publish_all(bus, bar(1.0))
            raise RuntimeError("crash mid-run")

    with pytest.raises(RuntimeError, match="crash mid-run"):
        crashing_run()
    assert _count(path, "runs") == 0
    assert _count(path, "market_data") == 0


def test_incompatible_legacy_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE fills (fill_id TEXT)")
        conn.commit()
    with pytest.raises(DataError, match="incompatible schema"):
        SQLiteWriter(str(path), "r1")


def test_non_database_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "not-a-db.db"
    path.write_bytes(b"this is not sqlite" * 100)
    with pytest.raises(DataError, match="not a usable SQLite database"):
        SQLiteWriter(str(path), "r1")
