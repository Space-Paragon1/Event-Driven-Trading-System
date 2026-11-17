"""SQLite persistence — an append-only, per-run event store."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from types import TracebackType
from typing import Any

from trading.bus.event_bus import EventBus
from trading.errors import DataError
from trading.events.types import (
    ApprovedOrderEvent,
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    PortfolioUpdateEvent,
    RiskVetoEvent,
    SignalEvent,
)

SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    config_json TEXT NOT NULL,
    report_json TEXT
);
CREATE TABLE IF NOT EXISTS market_data (
    run_id TEXT NOT NULL, symbol TEXT, timestamp TEXT,
    open REAL, high REAL, low REAL, close REAL, volume INTEGER
);
CREATE TABLE IF NOT EXISTS signals (
    run_id TEXT NOT NULL, symbol TEXT, timestamp TEXT, direction TEXT, strength REAL
);
CREATE TABLE IF NOT EXISTS orders (
    run_id TEXT NOT NULL, order_id TEXT, symbol TEXT, timestamp TEXT,
    order_type TEXT, direction TEXT, quantity INTEGER, price REAL
);
CREATE TABLE IF NOT EXISTS approved_orders (
    run_id TEXT NOT NULL, order_id TEXT, symbol TEXT, timestamp TEXT,
    order_type TEXT, direction TEXT, quantity INTEGER, price REAL
);
CREATE TABLE IF NOT EXISTS risk_vetos (
    run_id TEXT NOT NULL, order_id TEXT, symbol TEXT, timestamp TEXT, reason TEXT
);
CREATE TABLE IF NOT EXISTS fills (
    run_id TEXT NOT NULL, fill_id TEXT, order_id TEXT, symbol TEXT, timestamp TEXT,
    direction TEXT, quantity INTEGER, fill_price REAL, commission REAL
);
CREATE TABLE IF NOT EXISTS portfolio_updates (
    run_id TEXT NOT NULL, symbol TEXT, timestamp TEXT,
    position INTEGER, avg_cost REAL, realized_pnl REAL, unrealized_pnl REAL,
    cash REAL, equity REAL
);
CREATE INDEX IF NOT EXISTS idx_market_data_run ON market_data(run_id);
CREATE INDEX IF NOT EXISTS idx_signals_run ON signals(run_id);
CREATE INDEX IF NOT EXISTS idx_orders_run ON orders(run_id);
CREATE INDEX IF NOT EXISTS idx_approved_orders_run ON approved_orders(run_id);
CREATE INDEX IF NOT EXISTS idx_risk_vetos_run ON risk_vetos(run_id);
CREATE INDEX IF NOT EXISTS idx_fills_run ON fills(run_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_updates_run ON portfolio_updates(run_id);
"""


class SQLiteWriter:
    """Persists every event of a run, tagged with ``run_id``, to SQLite.

    Each backtest gets one row in ``runs`` (config and final report as JSON)
    plus one row per event in the per-type tables. Everything is written in
    a single transaction: committed on a clean exit and rolled back on an
    exception, so a crashed run leaves no partial data behind.

    Use as a context manager::

        with SQLiteWriter("trading.db", run_id) as db:
            db.start_run(symbol="AAPL", strategy="rsi", config={...})
            db.register(bus)
            ...
            db.finish_run(report.to_dict())

    Args:
        db_path: Database file, or ``":memory:"``.
        run_id:  Identifier stamped on every row.

    Raises:
        DataError: if the file holds a schema from an incompatible version.
    """

    def __init__(self, db_path: str, run_id: str) -> None:
        self.run_id = run_id
        self._conn = sqlite3.connect(db_path)
        self._init_schema(db_path)

    # ------------------------------------------------------------------
    # Lifecycle

    def __enter__(self) -> SQLiteWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()

    def close(self) -> None:
        """Commit and close (for use without ``with``)."""
        self._conn.commit()
        self._conn.close()

    def start_run(self, *, symbol: str, strategy: str, config: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO runs (run_id, started_at, symbol, strategy, config_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (self.run_id, _now(), symbol, strategy, json.dumps(config, sort_keys=True)),
        )

    def finish_run(self, report: dict[str, Any]) -> None:
        self._conn.execute(
            "UPDATE runs SET finished_at = ?, report_json = ? WHERE run_id = ?",
            (_now(), json.dumps(report, sort_keys=True), self.run_id),
        )

    # ------------------------------------------------------------------
    # Schema

    def _init_schema(self, db_path: str) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        has_tables = (
            self._conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone()
            is not None
        )
        if (version == 0 and has_tables) or version > SCHEMA_VERSION:
            self._conn.close()
            raise DataError(
                f"{db_path} uses an incompatible schema (version {version}, expected "
                f"{SCHEMA_VERSION}). Delete it or choose a different persistence.db_path."
            )
        self._conn.executescript(_SCHEMA)
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Event handlers

    def register(self, bus: EventBus) -> None:
        bus.subscribe(MarketDataEvent, self._on_market_data)
        bus.subscribe(SignalEvent, self._on_signal)
        bus.subscribe(OrderEvent, self._on_order)
        bus.subscribe(ApprovedOrderEvent, self._on_approved_order)
        bus.subscribe(RiskVetoEvent, self._on_risk_veto)
        bus.subscribe(FillEvent, self._on_fill)
        bus.subscribe(PortfolioUpdateEvent, self._on_portfolio_update)

    def _insert(self, table: str, *values: object) -> None:
        placeholders = ",".join("?" * (len(values) + 1))
        self._conn.execute(f"INSERT INTO {table} VALUES ({placeholders})", (self.run_id, *values))

    def _on_market_data(self, e: MarketDataEvent) -> None:
        self._insert(
            "market_data",
            e.symbol,
            e.timestamp.isoformat(),
            e.open,
            e.high,
            e.low,
            e.close,
            e.volume,
        )

    def _on_signal(self, e: SignalEvent) -> None:
        self._insert("signals", e.symbol, e.timestamp.isoformat(), e.direction.name, e.strength)

    def _on_order(self, e: OrderEvent) -> None:
        self._insert(
            "orders",
            e.order_id,
            e.symbol,
            e.timestamp.isoformat(),
            e.order_type.name,
            e.direction.name,
            e.quantity,
            e.price,
        )

    def _on_approved_order(self, e: ApprovedOrderEvent) -> None:
        self._insert(
            "approved_orders",
            e.order_id,
            e.symbol,
            e.timestamp.isoformat(),
            e.order_type.name,
            e.direction.name,
            e.quantity,
            e.price,
        )

    def _on_risk_veto(self, e: RiskVetoEvent) -> None:
        self._insert("risk_vetos", e.order_id, e.symbol, e.timestamp.isoformat(), e.reason)

    def _on_fill(self, e: FillEvent) -> None:
        self._insert(
            "fills",
            e.fill_id,
            e.order_id,
            e.symbol,
            e.timestamp.isoformat(),
            e.direction.name,
            e.quantity,
            e.fill_price,
            e.commission,
        )

    def _on_portfolio_update(self, e: PortfolioUpdateEvent) -> None:
        self._insert(
            "portfolio_updates",
            e.symbol,
            e.timestamp.isoformat(),
            e.position,
            e.avg_cost,
            e.realized_pnl,
            e.unrealized_pnl,
            e.cash,
            e.equity,
        )


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
