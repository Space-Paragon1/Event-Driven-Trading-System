"""SQLite persistence — writes every event to a local database."""

from __future__ import annotations

import sqlite3

from trading.bus.event_bus import EventBus
from trading.events.types import (
    ApprovedOrderEvent,
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    PortfolioUpdateEvent,
    RiskVetoEvent,
    SignalEvent,
)


class SQLiteWriter:
    """Subscribes to all event types and persists them to a SQLite database.

    Tables are created automatically on first use (``CREATE TABLE IF NOT
    EXISTS``).  Call :meth:`close` after the simulation to commit and close
    the connection.

    Args:
        db_path: File path for the SQLite database (default ``"trading.db"``).
                 Pass ``":memory:"`` in tests to avoid writing to disk.
    """

    def __init__(self, db_path: str = "trading.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS market_data (
                symbol TEXT, timestamp TEXT,
                open REAL, high REAL, low REAL, close REAL, volume INTEGER
            );
            CREATE TABLE IF NOT EXISTS signals (
                symbol TEXT, timestamp TEXT, direction TEXT, strength REAL
            );
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT, symbol TEXT, timestamp TEXT,
                order_type TEXT, direction TEXT, quantity INTEGER, price REAL
            );
            CREATE TABLE IF NOT EXISTS approved_orders (
                order_id TEXT, symbol TEXT, timestamp TEXT,
                order_type TEXT, direction TEXT, quantity INTEGER, price REAL
            );
            CREATE TABLE IF NOT EXISTS risk_vetos (
                order_id TEXT, symbol TEXT, timestamp TEXT, reason TEXT
            );
            CREATE TABLE IF NOT EXISTS fills (
                fill_id TEXT, order_id TEXT, symbol TEXT, timestamp TEXT,
                direction TEXT, quantity INTEGER, fill_price REAL, commission REAL
            );
            CREATE TABLE IF NOT EXISTS portfolio_updates (
                symbol TEXT, timestamp TEXT,
                position INTEGER, avg_cost REAL,
                realized_pnl REAL, unrealized_pnl REAL,
                cash REAL, equity REAL
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, bus: EventBus) -> None:
        bus.subscribe(MarketDataEvent, self._on_market_data)
        bus.subscribe(SignalEvent, self._on_signal)
        bus.subscribe(OrderEvent, self._on_order)
        bus.subscribe(ApprovedOrderEvent, self._on_approved_order)
        bus.subscribe(RiskVetoEvent, self._on_risk_veto)
        bus.subscribe(FillEvent, self._on_fill)
        bus.subscribe(PortfolioUpdateEvent, self._on_portfolio_update)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_market_data(self, e: MarketDataEvent) -> None:
        self._conn.execute(
            "INSERT INTO market_data VALUES (?,?,?,?,?,?,?)",
            (e.symbol, e.timestamp.isoformat(), e.open, e.high, e.low, e.close, e.volume),
        )

    def _on_signal(self, e: SignalEvent) -> None:
        self._conn.execute(
            "INSERT INTO signals VALUES (?,?,?,?)",
            (e.symbol, e.timestamp.isoformat(), e.direction.name, e.strength),
        )

    def _on_order(self, e: OrderEvent) -> None:
        self._conn.execute(
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?)",
            (e.order_id, e.symbol, e.timestamp.isoformat(),
             e.order_type.name, e.direction.name, e.quantity, e.price),
        )

    def _on_approved_order(self, e: ApprovedOrderEvent) -> None:
        self._conn.execute(
            "INSERT INTO approved_orders VALUES (?,?,?,?,?,?,?)",
            (e.order_id, e.symbol, e.timestamp.isoformat(),
             e.order_type.name, e.direction.name, e.quantity, e.price),
        )

    def _on_risk_veto(self, e: RiskVetoEvent) -> None:
        self._conn.execute(
            "INSERT INTO risk_vetos VALUES (?,?,?,?)",
            (e.order_id, e.symbol, e.timestamp.isoformat(), e.reason),
        )

    def _on_fill(self, e: FillEvent) -> None:
        self._conn.execute(
            "INSERT INTO fills VALUES (?,?,?,?,?,?,?,?)",
            (e.fill_id, e.order_id, e.symbol, e.timestamp.isoformat(),
             e.direction.name, e.quantity, e.fill_price, e.commission),
        )

    def _on_portfolio_update(self, e: PortfolioUpdateEvent) -> None:
        self._conn.execute(
            "INSERT INTO portfolio_updates VALUES (?,?,?,?,?,?,?,?)",
            (e.symbol, e.timestamp.isoformat(), e.position, e.avg_cost,
             e.realized_pnl, e.unrealized_pnl, e.cash, e.equity),
        )

    # ------------------------------------------------------------------

    def close(self) -> None:
        """Commit pending writes and close the database connection."""
        self._conn.commit()
        self._conn.close()
