"""Tests for Task 4.1 — Transaction and Statement frozen dataclasses."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from lloyds_expense.parser import Statement, Transaction

# ── Helpers ──────────────────────────────────────────────────────────────────


def make_transaction(
    *,
    tx_date: date = date(2026, 4, 1),
    description: str = "TEST PAYMENT",
    type_code: str = "DEB",
    amount: Decimal = Decimal("10.00"),
    direction: str = "out",
    running_balance: Decimal = Decimal("990.00"),
) -> Transaction:
    return Transaction(
        date=tx_date,
        description=description,
        type_code=type_code,
        amount=amount,
        direction=direction,  # type: ignore[arg-type]
        running_balance=running_balance,
    )


def make_statement(
    *,
    sort_code: str = "12-34-56",
    account_number: str = "12345678",
    period_start: date = date(2026, 4, 1),
    period_end: date = date(2026, 4, 30),
    opening_balance: Decimal = Decimal("1000.00"),
    closing_balance: Decimal = Decimal("800.00"),
    money_in_total: Decimal = Decimal("100.00"),
    money_out_total: Decimal = Decimal("300.00"),
    transactions: tuple[Transaction, ...] = (),
) -> Statement:
    return Statement(
        sort_code=sort_code,
        account_number=account_number,
        period_start=period_start,
        period_end=period_end,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        money_in_total=money_in_total,
        money_out_total=money_out_total,
        transactions=transactions,
    )


# ── Transaction field access ──────────────────────────────────────────────────


def test_transaction_date_field() -> None:
    tx = make_transaction(tx_date=date(2026, 3, 15))
    assert tx.date == date(2026, 3, 15)


def test_transaction_description_field() -> None:
    tx = make_transaction(description="SUPERMARKET PURCHASE")
    assert tx.description == "SUPERMARKET PURCHASE"


def test_transaction_type_code_field() -> None:
    tx = make_transaction(type_code="BGC")
    assert tx.type_code == "BGC"


def test_transaction_amount_field() -> None:
    tx = make_transaction(amount=Decimal("123.45"))
    assert tx.amount == Decimal("123.45")


def test_transaction_direction_in() -> None:
    tx = make_transaction(direction="in", amount=Decimal("500.00"))
    assert tx.direction == "in"


def test_transaction_direction_out() -> None:
    tx = make_transaction(direction="out")
    assert tx.direction == "out"


def test_transaction_running_balance_field() -> None:
    tx = make_transaction(running_balance=Decimal("2500.99"))
    assert tx.running_balance == Decimal("2500.99")


# ── Transaction immutability ──────────────────────────────────────────────────


def test_transaction_is_frozen() -> None:
    tx = make_transaction()
    with pytest.raises(AttributeError):
        tx.description = "MODIFIED"  # type: ignore[misc]


def test_transaction_amount_is_frozen() -> None:
    tx = make_transaction(amount=Decimal("50.00"))
    with pytest.raises(AttributeError):
        tx.amount = Decimal("0.00")  # type: ignore[misc]


def test_transaction_direction_is_frozen() -> None:
    tx = make_transaction(direction="out")
    with pytest.raises(AttributeError):
        tx.direction = "in"  # type: ignore[misc]


# ── Transaction types ─────────────────────────────────────────────────────────


def test_transaction_amount_is_decimal_not_float() -> None:
    tx = make_transaction(amount=Decimal("99.99"))
    assert isinstance(tx.amount, Decimal)
    assert not isinstance(tx.amount, float)


def test_transaction_running_balance_is_decimal_not_float() -> None:
    tx = make_transaction(running_balance=Decimal("1234.56"))
    assert isinstance(tx.running_balance, Decimal)
    assert not isinstance(tx.running_balance, float)


def test_transaction_date_is_date_object() -> None:
    tx = make_transaction(tx_date=date(2026, 1, 31))
    assert isinstance(tx.date, date)


def test_transaction_description_is_str() -> None:
    tx = make_transaction(description="SOME PAYEE")
    assert isinstance(tx.description, str)


def test_transaction_type_code_is_str() -> None:
    tx = make_transaction(type_code="FPI")
    assert isinstance(tx.type_code, str)


# ── Transaction equality and hashing ─────────────────────────────────────────


def test_transaction_equality() -> None:
    tx1 = make_transaction(description="SAME", amount=Decimal("10.00"))
    tx2 = make_transaction(description="SAME", amount=Decimal("10.00"))
    assert tx1 == tx2


def test_transaction_inequality_on_amount() -> None:
    tx1 = make_transaction(amount=Decimal("10.00"))
    tx2 = make_transaction(amount=Decimal("20.00"))
    assert tx1 != tx2


def test_transaction_inequality_on_description() -> None:
    tx1 = make_transaction(description="ALPHA")
    tx2 = make_transaction(description="BETA")
    assert tx1 != tx2


def test_transaction_inequality_on_direction() -> None:
    tx1 = make_transaction(direction="in")
    tx2 = make_transaction(direction="out")
    assert tx1 != tx2


def test_transaction_is_hashable() -> None:
    tx = make_transaction()
    assert hash(tx) is not None
    s: set[Transaction] = {tx}
    assert tx in s


def test_two_equal_transactions_have_same_hash() -> None:
    tx1 = make_transaction(description="SAME", amount=Decimal("5.00"))
    tx2 = make_transaction(description="SAME", amount=Decimal("5.00"))
    assert hash(tx1) == hash(tx2)


def test_transaction_can_be_used_as_dict_key() -> None:
    tx = make_transaction()
    d: dict[Transaction, str] = {tx: "label"}
    assert d[tx] == "label"


# ── Transaction amount precision ──────────────────────────────────────────────


def test_transaction_amount_preserves_decimal_precision() -> None:
    tx = make_transaction(amount=Decimal("1000.00"))
    assert tx.amount == Decimal("1000.00")
    assert str(tx.amount) == "1000.00"


def test_transaction_large_amount() -> None:
    tx = make_transaction(amount=Decimal("99999.99"))
    assert tx.amount == Decimal("99999.99")


def test_transaction_zero_amount() -> None:
    tx = make_transaction(amount=Decimal("0.00"))
    assert tx.amount == Decimal("0.00")


# ── Statement field access ────────────────────────────────────────────────────


def test_statement_sort_code_field() -> None:
    stmt = make_statement(sort_code="77-88-99")
    assert stmt.sort_code == "77-88-99"


def test_statement_account_number_field() -> None:
    stmt = make_statement(account_number="87654321")
    assert stmt.account_number == "87654321"


def test_statement_period_start_field() -> None:
    stmt = make_statement(period_start=date(2026, 1, 1))
    assert stmt.period_start == date(2026, 1, 1)


def test_statement_period_end_field() -> None:
    stmt = make_statement(period_end=date(2026, 1, 31))
    assert stmt.period_end == date(2026, 1, 31)


def test_statement_opening_balance_field() -> None:
    stmt = make_statement(opening_balance=Decimal("2500.00"))
    assert stmt.opening_balance == Decimal("2500.00")


def test_statement_closing_balance_field() -> None:
    stmt = make_statement(closing_balance=Decimal("1800.00"))
    assert stmt.closing_balance == Decimal("1800.00")


def test_statement_money_in_total_field() -> None:
    stmt = make_statement(money_in_total=Decimal("500.00"))
    assert stmt.money_in_total == Decimal("500.00")


def test_statement_money_out_total_field() -> None:
    stmt = make_statement(money_out_total=Decimal("700.00"))
    assert stmt.money_out_total == Decimal("700.00")


def test_statement_transactions_field_empty() -> None:
    stmt = make_statement(transactions=())
    assert stmt.transactions == ()
    assert len(stmt.transactions) == 0


# ── Statement immutability ────────────────────────────────────────────────────


def test_statement_is_frozen() -> None:
    stmt = make_statement()
    with pytest.raises(AttributeError):
        stmt.sort_code = "00-00-00"  # type: ignore[misc]


def test_statement_opening_balance_is_frozen() -> None:
    stmt = make_statement()
    with pytest.raises(AttributeError):
        stmt.opening_balance = Decimal("0.00")  # type: ignore[misc]


def test_statement_transactions_tuple_is_frozen() -> None:
    stmt = make_statement()
    with pytest.raises(AttributeError):
        stmt.transactions = ()  # type: ignore[misc]


# ── Statement monetary field types ────────────────────────────────────────────


def test_statement_opening_balance_is_decimal() -> None:
    stmt = make_statement(opening_balance=Decimal("100.00"))
    assert isinstance(stmt.opening_balance, Decimal)


def test_statement_closing_balance_is_decimal() -> None:
    stmt = make_statement(closing_balance=Decimal("90.00"))
    assert isinstance(stmt.closing_balance, Decimal)


def test_statement_money_in_total_is_decimal() -> None:
    stmt = make_statement(money_in_total=Decimal("50.00"))
    assert isinstance(stmt.money_in_total, Decimal)


def test_statement_money_out_total_is_decimal() -> None:
    stmt = make_statement(money_out_total=Decimal("60.00"))
    assert isinstance(stmt.money_out_total, Decimal)


# ── Statement with transactions ───────────────────────────────────────────────


def test_statement_stores_single_transaction() -> None:
    tx = make_transaction(description="RENT PAYMENT", amount=Decimal("800.00"), direction="out")
    stmt = make_statement(transactions=(tx,))
    assert len(stmt.transactions) == 1
    assert stmt.transactions[0] is tx


def test_statement_stores_multiple_transactions() -> None:
    tx1 = make_transaction(description="SALARY", direction="in", amount=Decimal("2000.00"))
    tx2 = make_transaction(description="RENT", direction="out", amount=Decimal("900.00"))
    tx3 = make_transaction(description="FOOD", direction="out", amount=Decimal("150.00"))
    stmt = make_statement(transactions=(tx1, tx2, tx3))
    assert len(stmt.transactions) == 3
    assert stmt.transactions[0] is tx1
    assert stmt.transactions[1] is tx2
    assert stmt.transactions[2] is tx3


def test_statement_transactions_preserves_order() -> None:
    tx_a = make_transaction(description="FIRST", amount=Decimal("1.00"))
    tx_b = make_transaction(description="SECOND", amount=Decimal("2.00"))
    tx_c = make_transaction(description="THIRD", amount=Decimal("3.00"))
    stmt = make_statement(transactions=(tx_a, tx_b, tx_c))
    descriptions = [tx.description for tx in stmt.transactions]
    assert descriptions == ["FIRST", "SECOND", "THIRD"]


def test_statement_transactions_is_tuple() -> None:
    tx = make_transaction()
    stmt = make_statement(transactions=(tx,))
    assert isinstance(stmt.transactions, tuple)


# ── Statement equality ────────────────────────────────────────────────────────


def test_statement_equality() -> None:
    stmt1 = make_statement(sort_code="12-34-56", account_number="11111111")
    stmt2 = make_statement(sort_code="12-34-56", account_number="11111111")
    assert stmt1 == stmt2


def test_statement_inequality_on_account_number() -> None:
    stmt1 = make_statement(account_number="11111111")
    stmt2 = make_statement(account_number="22222222")
    assert stmt1 != stmt2


def test_statement_inequality_on_transactions() -> None:
    tx = make_transaction(amount=Decimal("50.00"))
    stmt1 = make_statement(transactions=())
    stmt2 = make_statement(transactions=(tx,))
    assert stmt1 != stmt2


def test_statement_is_hashable() -> None:
    stmt = make_statement()
    assert hash(stmt) is not None


# ── Cross-year period boundary ────────────────────────────────────────────────


def test_statement_period_can_span_year_boundary() -> None:
    stmt = make_statement(
        period_start=date(2025, 12, 15),
        period_end=date(2026, 1, 14),
    )
    assert stmt.period_start.year == 2025
    assert stmt.period_end.year == 2026


def test_transaction_date_in_december() -> None:
    tx = make_transaction(tx_date=date(2025, 12, 31))
    assert tx.date == date(2025, 12, 31)
    assert tx.date.month == 12


def test_transaction_date_in_january() -> None:
    tx = make_transaction(tx_date=date(2026, 1, 1))
    assert tx.date == date(2026, 1, 1)
    assert tx.date.month == 1


# ── All Lloyds type codes stored verbatim ────────────────────────────────────


@pytest.mark.parametrize(
    "type_code",
    [
        "FPO",
        "FPI",
        "DD",
        "DEB",
        "BGC",
        "BP",
        "CHG",
        "CHQ",
        "COR",
        "CPT",
        "DEP",
        "FEE",
        "MPI",
        "MPO",
        "PAY",
        "SO",
        "TFR",
    ],
)
def test_transaction_accepts_known_type_codes(type_code: str) -> None:
    tx = make_transaction(type_code=type_code)
    assert tx.type_code == type_code


# ── Transaction direction semantics ──────────────────────────────────────────


def test_money_in_transaction_amount_is_positive() -> None:
    tx = make_transaction(direction="in", amount=Decimal("250.00"))
    assert tx.direction == "in"
    assert tx.amount > Decimal("0")


def test_money_out_transaction_amount_is_positive() -> None:
    """Outflows are stored as positive Decimal; direction encodes the sign."""
    tx = make_transaction(direction="out", amount=Decimal("75.50"))
    assert tx.direction == "out"
    assert tx.amount > Decimal("0")
