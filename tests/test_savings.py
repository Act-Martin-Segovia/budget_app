from budget_app.app.helper_functions import (
    get_current_savings_balances,
    get_monthly_savings_contributions,
    get_savings_balance_series,
    set_account_month_balances,
)
from budget_app.db.db import (
    add_savings_funded_expense,
    add_savings_movement,
    add_transaction,
    close_month,
    get_connection,
    open_month,
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


def _create_savings_account(
    name: str = "TFSA-RBC", linked_bank_account_id: int | None = None
) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO savings_accounts (
            name,
            institution,
            account_type,
            linked_bank_account_id,
            active,
            effective_from_month_id
        )
        VALUES (?, 'RBC', 'tfsa', ?, 1, '2026-01')
        """,
        (name, linked_bank_account_id),
    )
    conn.commit()
    conn.close()
    return cursor.lastrowid


def test_get_savings_balance_series_includes_ledger_and_matching_legacy_savings_transactions(
    initialized_db,
):
    bank_account_id = _create_bank_account()
    savings_account_id = _create_savings_account(
        "TFSA-RBC", linked_bank_account_id=bank_account_id
    )
    conn = get_connection()
    conn.executemany(
        """
        INSERT INTO months (month_id, starting_balance, status)
        VALUES (?, 0, 'open')
        """,
        [("2026-03",), ("2026-04",)],
    )
    conn.commit()
    conn.close()

    tx_id = add_transaction(
        date="2026-04-15",
        month_id="2026-04",
        amount=-200.0,
        category="Savings",
        subcategory="TFSA-RBC",
        payment_method="debit",
        bank_account_id=bank_account_id,
        savings_account_id=savings_account_id,
        note="April contribution",
    )
    add_savings_movement(
        date="2026-04-15",
        month_id="2026-04",
        savings_account_id=savings_account_id,
        amount=200.0,
        movement_type="contribution",
        linked_transaction_id=tx_id,
        note="April contribution",
    )
    add_transaction(
        date="2026-03-10",
        month_id="2026-03",
        amount=-150.0,
        category="Savings",
        subcategory="TFSA-RBC",
        payment_method="debit",
        bank_account_id=bank_account_id,
        note="Legacy contribution",
    )

    series = get_savings_balance_series()

    assert series == [
        {
            "date": "2026-03-10",
            "savings_account_name": "TFSA-RBC",
            "balance": 150.0,
            "movement_amount": 150.0,
        },
        {
            "date": "2026-04-15",
            "savings_account_name": "TFSA-RBC",
            "balance": 350.0,
            "movement_amount": 200.0,
        },
    ]


def test_opening_balance_counts_for_current_balance_but_not_contribution_history(
    initialized_db,
):
    bank_account_id = _create_bank_account()
    savings_account_id = _create_savings_account(
        "TFSA-RBC", linked_bank_account_id=bank_account_id
    )
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO months (month_id, starting_balance, status)
        VALUES ('2026-04', 0, 'open')
        """
    )
    conn.commit()
    conn.close()

    add_savings_movement(
        date="2026-04-01",
        month_id="2026-04",
        savings_account_id=savings_account_id,
        amount=10000.0,
        movement_type="opening_balance",
        note="Opening balance before app tracking",
    )
    add_savings_movement(
        date="2026-04-15",
        month_id="2026-04",
        savings_account_id=savings_account_id,
        amount=500.0,
        movement_type="contribution",
        note="April contribution",
    )

    assert get_current_savings_balances() == [
        {
            "savings_account_name": "TFSA-RBC",
            "institution": "RBC",
            "account_type": "tfsa",
            "balance": 10500.0,
        }
    ]
    assert get_monthly_savings_contributions() == [
        {
            "month_id": "2026-04",
            "savings_account_name": "TFSA-RBC",
            "contribution_amount": 500.0,
        }
    ]


def test_add_savings_funded_expense_creates_transfer_and_preserves_bank_cash(
    initialized_db,
):
    bank_account_id = _create_bank_account()
    savings_account_id = _create_savings_account(
        "Vacation Fund", linked_bank_account_id=bank_account_id
    )

    open_month("2026-04", 1000.0)
    set_account_month_balances("2026-04", {bank_account_id: 1000.0})

    transfer_tx_id, expense_tx_id = add_savings_funded_expense(
        date="2026-04-20",
        month_id="2026-04",
        amount=300.0,
        category="Variable",
        subcategory="Vacation",
        bank_account_id=bank_account_id,
        savings_account_id=savings_account_id,
        note="Hotel booking",
    )

    ending_balance = close_month("2026-04")

    conn = get_connection()
    tx_rows = conn.execute(
        """
        SELECT category, subcategory, amount, bank_account_id, savings_account_id, note
        FROM transactions
        WHERE id IN (?, ?)
        ORDER BY id
        """,
        (transfer_tx_id, expense_tx_id),
    ).fetchall()
    movement = conn.execute(
        """
        SELECT amount, movement_type, linked_transaction_id
        FROM savings_movements
        WHERE savings_account_id = ?
        """,
        (savings_account_id,),
    ).fetchone()
    account_balance = conn.execute(
        """
        SELECT ending_balance
        FROM account_month_balances
        WHERE month_id = '2026-04' AND bank_account_id = ?
        """,
        (bank_account_id,),
    ).fetchone()
    conn.close()

    assert [dict(row) for row in tx_rows] == [
        {
            "category": "Transfer",
            "subcategory": "From savings",
            "amount": 300.0,
            "bank_account_id": bank_account_id,
            "savings_account_id": savings_account_id,
            "note": "Auto transfer from savings: Hotel booking",
        },
        {
            "category": "Variable",
            "subcategory": "Vacation",
            "amount": -300.0,
            "bank_account_id": bank_account_id,
            "savings_account_id": savings_account_id,
            "note": "Hotel booking",
        },
    ]
    assert dict(movement) == {
        "amount": -300.0,
        "movement_type": "withdrawal",
        "linked_transaction_id": transfer_tx_id,
    }
    assert ending_balance == 1000.0
    assert dict(account_balance) == {"ending_balance": 1000.0}
