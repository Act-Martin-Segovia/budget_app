import sqlite3

from budget_app.app.helper_functions import (
    get_fixed_expenses,
    preview_fixed_expenses_for_month,
    set_account_month_balances,
    upsert_fixed_expense,
)
from budget_app.db.db import (
    close_month,
    get_connection,
    migrate_db,
    open_month,
    set_db_path,
)


def _create_bank_account(name: str = "Checking") -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO bank_accounts (name, active, effective_from_month_id)
        VALUES (?, 1, '2026-01')
        """,
        (name,),
    )
    conn.commit()
    conn.close()
    return cursor.lastrowid


def _create_credit_card(bank_account_id: int, name: str = "Visa") -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO credit_cards (
            name,
            bank_account_id,
            statement_close_day,
            due_day,
            active,
            effective_from_month_id
        )
        VALUES (?, ?, 20, 15, 1, '2026-01')
        """,
        (name, bank_account_id),
    )
    conn.commit()
    conn.close()
    return cursor.lastrowid


def test_migrate_db_keeps_legacy_fixed_expenses_working_as_debit(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE months (
            month_id TEXT PRIMARY KEY,
            starting_balance REAL NOT NULL,
            ending_balance REAL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            month_id TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            payment_method TEXT,
            note TEXT,
            type TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE fixed_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            due_day INTEGER NOT NULL,
            category TEXT NOT NULL DEFAULT 'Fixed',
            subcategory TEXT,
            bank_account_id INTEGER,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE income_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            due_day INTEGER NOT NULL,
            category TEXT NOT NULL DEFAULT 'Income',
            subcategory TEXT,
            bank_account_id INTEGER,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        """
        INSERT INTO fixed_expenses (
            name, amount, due_day, category, subcategory, bank_account_id, active
        )
        VALUES ('Rent', 1200.0, 1, 'Fixed', 'Housing', 1, 1)
        """
    )
    conn.commit()
    conn.close()

    set_db_path(db_path)
    migrate_db()
    account_id = _create_bank_account()

    expenses = [dict(row) for row in get_fixed_expenses()]
    assert expenses == [
        {
            "id": 1,
            "name": "Rent",
            "amount": 1200.0,
            "due_day": 1,
            "subcategory": "Housing",
            "payment_method": "debit",
            "bank_account_id": account_id,
            "credit_card_id": None,
            "active": 1,
        }
    ]

    open_month("2026-04", 3000.0)

    conn = get_connection()
    tx = conn.execute(
        """
        SELECT
            amount,
            payment_method,
            bank_account_id,
            credit_card_id,
            statement_month_id,
            due_month_id,
            due_date,
            note
        FROM transactions
        WHERE month_id = '2026-04'
        """
    ).fetchone()
    conn.close()

    assert dict(tx) == {
        "amount": -1200.0,
        "payment_method": "debit",
        "bank_account_id": account_id,
        "credit_card_id": None,
        "statement_month_id": None,
        "due_month_id": None,
        "due_date": None,
        "note": "Fixed expense: Rent",
    }


def test_open_month_materializes_credit_card_fixed_expense(initialized_db):
    account_id = _create_bank_account()
    card_id = _create_credit_card(account_id)

    upsert_fixed_expense(
        "Gym",
        75.0,
        10,
        "Health",
        "credit_card",
        None,
        card_id,
    )

    open_month("2026-04", 3000.0)

    conn = get_connection()
    tx = conn.execute(
        """
        SELECT
            amount,
            payment_method,
            bank_account_id,
            credit_card_id,
            statement_month_id,
            due_month_id,
            due_date,
            note
        FROM transactions
        WHERE month_id = '2026-04'
        """
    ).fetchone()
    conn.close()

    assert dict(tx) == {
        "amount": -75.0,
        "payment_method": "credit_card",
        "bank_account_id": None,
        "credit_card_id": card_id,
        "statement_month_id": "2026-04",
        "due_month_id": "2026-05",
        "due_date": "2026-05-15",
        "note": "Fixed expense: Gym",
    }


def test_preview_fixed_expenses_flags_invalid_credit_card_for_month(initialized_db):
    account_id = _create_bank_account()
    card_id = _create_credit_card(account_id)

    conn = get_connection()
    conn.execute(
        """
        UPDATE credit_cards
        SET effective_to_month_id = '2026-03'
        WHERE id = ?
        """,
        (card_id,),
    )
    conn.commit()
    conn.close()

    upsert_fixed_expense(
        "Streaming",
        19.99,
        12,
        "Subscriptions",
        "credit_card",
        None,
        card_id,
    )

    preview, total = preview_fixed_expenses_for_month("2026-04")

    assert total == -19.99
    assert len(preview) == 1
    assert preview[0]["issue"] == "Selected credit card is not active for this month."


def test_close_month_excludes_credit_card_fixed_expenses_from_cash_account_balance(
    initialized_db,
):
    account_id = _create_bank_account()
    card_id = _create_credit_card(account_id)

    upsert_fixed_expense(
        "Rent",
        1200.0,
        1,
        "Housing",
        "debit",
        account_id,
        None,
    )
    upsert_fixed_expense(
        "Gym",
        75.0,
        10,
        "Health",
        "credit_card",
        None,
        card_id,
    )

    open_month("2026-04", 3000.0)
    set_account_month_balances("2026-04", {account_id: 3000.0})

    ending_balance = close_month("2026-04")

    conn = get_connection()
    month_row = conn.execute(
        """
        SELECT ending_balance, status
        FROM months
        WHERE month_id = '2026-04'
        """
    ).fetchone()
    account_row = conn.execute(
        """
        SELECT starting_balance, ending_balance
        FROM account_month_balances
        WHERE month_id = '2026-04' AND bank_account_id = ?
        """,
        (account_id,),
    ).fetchone()
    conn.close()

    assert ending_balance == 1725.0
    assert dict(month_row) == {"ending_balance": 1725.0, "status": "closed"}
    assert dict(account_row) == {
        "starting_balance": 3000.0,
        "ending_balance": 1800.0,
    }
