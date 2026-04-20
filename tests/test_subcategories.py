from budget_app.app.helper_functions import get_known_subcategories
from budget_app.db.db import get_connection


def test_get_known_subcategories_deduplicates_and_trims_values(initialized_db):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO months (month_id, starting_balance, status)
        VALUES ('2026-04', 0, 'open')
        """
    )
    conn.executemany(
        """
        INSERT INTO transactions (
            date, month_id, amount, category, subcategory, type
        )
        VALUES (?, '2026-04', ?, ?, ?, 'normal')
        """,
        [
            ("2026-04-01", -10.0, "Variable", "Groceries"),
            ("2026-04-02", -5.0, "Variable", "  Groceries  "),
            ("2026-04-03", 100.0, "Income", "Salary"),
            ("2026-04-04", -25.0, "Savings", ""),
        ],
    )
    conn.execute(
        """
        INSERT INTO fixed_expenses (
            name, amount, due_day, category, subcategory, payment_method, active
        )
        VALUES ('Rent', 1200.0, 1, 'Fixed', 'Housing', 'debit', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO income_sources (
            name, amount, due_day, category, subcategory, active
        )
        VALUES ('Primary Job', 2500.0, 15, 'Income', '  Salary  ', 1)
        """
    )
    conn.commit()
    conn.close()

    assert get_known_subcategories() == ["Groceries", "Housing", "Salary"]


def test_get_known_subcategories_filters_by_category(initialized_db):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO months (month_id, starting_balance, status)
        VALUES ('2026-04', 0, 'open')
        """
    )
    conn.executemany(
        """
        INSERT INTO transactions (
            date, month_id, amount, category, subcategory, type
        )
        VALUES (?, '2026-04', ?, ?, ?, 'normal')
        """,
        [
            ("2026-04-01", -10.0, "Variable", "Groceries"),
            ("2026-04-02", -20.0, "Savings", "Emergency Fund"),
            ("2026-04-03", 2000.0, "Income", "Bonus"),
        ],
    )
    conn.execute(
        """
        INSERT INTO income_sources (
            name, amount, due_day, category, subcategory, active
        )
        VALUES ('Primary Job', 2500.0, 15, 'Income', 'Salary', 1)
        """
    )
    conn.commit()
    conn.close()

    assert get_known_subcategories("Variable") == ["Groceries"]
    assert get_known_subcategories("Savings") == ["Emergency Fund"]
    assert get_known_subcategories("Income") == ["Bonus", "Salary"]
