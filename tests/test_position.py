"""Tests for Position accounting and PositionBook, including property-based invariants."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.factories import fill
from trading.events.types import Direction
from trading.portfolio.position import Position, PositionBook

# --------------------------------------------------------------------------- Position


def test_open_long_sets_avg_cost() -> None:
    p = Position()
    assert p.apply(100, 150.0) == 0.0
    assert (p.quantity, p.avg_cost) == (100, 150.0)


def test_adding_blends_avg_cost() -> None:
    p = Position()
    p.apply(100, 100.0)
    p.apply(300, 120.0)
    assert p.quantity == 400
    assert p.avg_cost == pytest.approx(115.0)


def test_partial_close_realizes_and_keeps_avg_cost() -> None:
    p = Position()
    p.apply(100, 100.0)
    realized = p.apply(-40, 110.0)
    assert realized == pytest.approx(400.0)
    assert (p.quantity, p.avg_cost) == (60, 100.0)


def test_full_close_resets_avg_cost() -> None:
    p = Position()
    p.apply(100, 100.0)
    p.apply(-100, 90.0)
    assert (p.quantity, p.avg_cost) == (0, 0.0)
    assert p.realized_pnl == pytest.approx(-1000.0)


def test_short_from_flat_does_not_realize_anything() -> None:
    """Regression: the old tracker booked the full sale notional as realized P&L."""
    p = Position()
    assert p.apply(-100, 152.92) == 0.0
    assert (p.quantity, p.avg_cost) == (-100, 152.92)


def test_covering_short_realizes_profit_when_price_falls() -> None:
    p = Position()
    p.apply(-100, 150.0)
    assert p.apply(100, 140.0) == pytest.approx(1000.0)
    assert p.quantity == 0


def test_short_unrealized_pnl_sign() -> None:
    p = Position()
    p.apply(-100, 150.0)
    assert p.unrealized_pnl(145.0) == pytest.approx(500.0)
    assert p.unrealized_pnl(155.0) == pytest.approx(-500.0)


def test_flip_long_to_short_realizes_and_reopens_at_fill_price() -> None:
    p = Position()
    p.apply(100, 100.0)
    realized = p.apply(-250, 110.0)
    assert realized == pytest.approx(1000.0)
    assert (p.quantity, p.avg_cost) == (-150, 110.0)


def test_zero_quantity_fill_is_noop() -> None:
    p = Position(quantity=10, avg_cost=5.0)
    assert p.apply(0, 99.0) == 0.0
    assert (p.quantity, p.avg_cost) == (10, 5.0)


fills_strategy = st.lists(
    st.tuples(
        st.integers(min_value=-500, max_value=500).filter(bool),
        st.floats(min_value=1.0, max_value=1_000.0, allow_nan=False),
    ),
    min_size=1,
    max_size=40,
)


@given(fills=fills_strategy, mark=st.floats(min_value=1.0, max_value=1_000.0))
def test_pnl_conservation(fills: list[tuple[int, float]], mark: float) -> None:
    """Realized + unrealized P&L always equals the cash-flow P&L of the fills."""
    p = Position()
    cash_flow = 0.0
    for qty, price in fills:
        p.apply(qty, price)
        cash_flow -= qty * price
    mark_to_market = cash_flow + p.quantity * mark
    total = p.realized_pnl + p.unrealized_pnl(mark)
    assert total == pytest.approx(mark_to_market, rel=1e-9, abs=1e-6)
    if p.quantity == 0:
        assert p.avg_cost == 0.0


# --------------------------------------------------------------------------- PositionBook


def test_book_projects_working_orders() -> None:
    book = PositionBook()
    book.add_working("O1", "AAPL", 100)
    assert book.filled("AAPL") == 0
    assert book.projected("AAPL") == 100


def test_book_fill_moves_working_to_filled() -> None:
    book = PositionBook()
    book.add_working("O1", "AAPL", 100)
    book.on_fill(fill(Direction.BUY, 100, order_id="O1"))
    assert book.filled("AAPL") == 100
    assert book.projected("AAPL") == 100


def test_book_cancel_removes_working_order() -> None:
    book = PositionBook()
    book.add_working("O1", "AAPL", -50)
    book.cancel("O1")
    assert book.projected("AAPL") == 0


def test_book_is_per_symbol() -> None:
    book = PositionBook()
    book.add_working("O1", "AAPL", 100)
    book.add_working("O2", "MSFT", -30)
    assert book.projected("AAPL") == 100
    assert book.projected("MSFT") == -30
