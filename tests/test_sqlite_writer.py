"""Tests for SQLiteWriter."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from trading.bus.event_bus import EventBus
from trading.events.types import (
    ApprovedOrderEvent,
    Direction,
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    OrderType,
    PortfolioUpdateEvent,
    RiskVetoEvent,
    SignalEvent,
)
from trading.persistence.sqlite_writer import SQLiteWriter

_TS = datetime(2024, 1, 2, 9, 30)


def _writer() -> SQLiteWriter:
    return SQLiteWriter(db_path=":memory:")


def _bus_with_writer() -> tuple[EventBus, SQLiteWriter]:
    bus = EventBus()
    w = _writer()
    w.register(bus)
    return bus, w


def test_tables_created() -> None:
    w = _writer()
    tables = {
        row[0]
        for row in w._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    expected = {"market_data", "signals", "orders", "approved_orders",
                "risk_vetos", "fills", "portfolio_updates"}
    assert expected.issubset(tables)
    w.close()


def test_market_data_row_inserted() -> None:
    bus, w = _bus_with_writer()
    bus.publish(MarketDataEvent("AAPL", _TS, 150.0, 151.0, 149.0, 150.5, 1_000_000))
    bus.run()
    count = w._conn.execute("SELECT COUNT(*) FROM market_data").fetchone()[0]
    assert count == 1
    w.close()


def test_signal_row_inserted() -> None:
    bus, w = _bus_with_writer()
    bus.publish(SignalEvent("AAPL", _TS, Direction.BUY, 0.75))
    bus.run()
    assert w._conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 1
    w.close()


def test_order_row_inserted() -> None:
    bus, w = _bus_with_writer()
    bus.publish(OrderEvent("oid", "AAPL", _TS, OrderType.MARKET, Direction.BUY, 100, 150.0))
    bus.run()
    assert w._conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 1
    w.close()


def test_approved_order_row_inserted() -> None:
    bus, w = _bus_with_writer()
    bus.publish(ApprovedOrderEvent("oid", "AAPL", _TS, OrderType.MARKET, Direction.BUY, 100, 150.0))
    bus.run()
    assert w._conn.execute("SELECT COUNT(*) FROM approved_orders").fetchone()[0] == 1
    w.close()


def test_risk_veto_row_inserted() -> None:
    bus, w = _bus_with_writer()
    bus.publish(RiskVetoEvent("oid", "AAPL", _TS, "test reason"))
    bus.run()
    assert w._conn.execute("SELECT COUNT(*) FROM risk_vetos").fetchone()[0] == 1
    w.close()


def test_fill_row_inserted() -> None:
    bus, w = _bus_with_writer()
    bus.publish(FillEvent("fid", "oid", "AAPL", _TS, Direction.BUY, 100, 150.5, 1.0))
    bus.run()
    assert w._conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0] == 1
    w.close()


def test_portfolio_update_row_inserted() -> None:
    bus, w = _bus_with_writer()
    bus.publish(PortfolioUpdateEvent("AAPL", _TS, 100, 150.0, 0.0, 500.0, 85_000.0, 100_500.0))
    bus.run()
    assert w._conn.execute("SELECT COUNT(*) FROM portfolio_updates").fetchone()[0] == 1
    w.close()
