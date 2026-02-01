import sys
from pathlib import Path
from datetime import date
from dateutil.relativedelta import relativedelta

from budget_app.utils import get_repo_root

from budget_app.db.db import (
    get_connection,
)

ROOT = get_repo_root()


# ======================================================
# Helpers
# ======================================================


def month_id_from_date(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def current_month_id() -> str:
    return month_id_from_date(date.today())


def list_known_months() -> list[str]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT month_id FROM months ORDER BY month_id"
    ).fetchall()
    conn.close()
    return [r["month_id"] for r in rows]


def get_month_status(month_id: str) -> str | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT status FROM months WHERE month_id = ?", (month_id,)
    ).fetchone()
    conn.close()
    return row["status"] if row else None


def get_previous_month_ending_balance(month_id: str) -> float | None:
    conn = get_connection()

    row = conn.execute(
        """
        SELECT ending_balance
        FROM months
        WHERE month_id < ?
          AND status = 'closed'
        ORDER BY month_id DESC
        LIMIT 1
        """,
        (month_id,),
    ).fetchone()

    conn.close()

    return row["ending_balance"] if row else None


def get_month_snapshot(month_id: str) -> dict:
    conn = get_connection()

    month = conn.execute(
        """
        SELECT starting_balance, status
        FROM months
        WHERE month_id = ?
        """,
        (month_id,),
    ).fetchone()

    net = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS net
        FROM transactions
        WHERE month_id = ?
        """,
        (month_id,),
    ).fetchone()["net"]

    conn.close()

    return {
        "starting_balance": month["starting_balance"],
        "net": net,
        "projected_ending": month["starting_balance"] + net,
        "status": month["status"],
    }


def get_month_totals_by_category(month_id: str) -> dict[str, float]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT category, COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE month_id = ?
        GROUP BY category
        """,
        (month_id,),
    ).fetchall()
    conn.close()
    return {r["category"]: r["total"] for r in rows}


def get_total_income(month_id: str) -> float:
    conn = get_connection()
    income = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS income
        FROM transactions
        WHERE month_id = ? AND category = 'Income'
        """,
        (month_id,),
    ).fetchone()["income"]
    conn.close()
    return income


def get_active_objectives() -> dict[str, float]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT category, percentage
        FROM budget_objectives
        WHERE active = 1 AND subcategory IS NULL
        """
    ).fetchall()
    conn.close()
    return {r["category"]: r["percentage"] for r in rows}


def get_category_actual(month_id: str, category: str) -> float:
    conn = get_connection()
    total = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE month_id = ? AND category = ?
        """,
        (month_id, category),
    ).fetchone()["total"]
    conn.close()
    return abs(total)


def get_category_planned(month_id: str, category: str) -> float:
    income = get_total_income(month_id)
    pct = get_active_objectives().get(category)
    if pct is None:
        raise RuntimeError(f"No objective defined for category {category}")
    return income * pct


def generate_month_options(
    start: date, months_ahead: int = 6
) -> list[str]:
    return [
        f"{(start + relativedelta(months=i)).year}-"
        f"{(start + relativedelta(months=i)).month:02d}"
        for i in range(months_ahead + 1)
    ]


def get_fixed_expenses():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, name, amount, due_day, subcategory, active
        FROM fixed_expenses
        WHERE active = 1
        ORDER BY due_day
        """
    ).fetchall()
    conn.close()
    return rows


def upsert_fixed_expense(name, amount, due_day, subcategory):
    conn = get_connection()

    conn.execute(
        """
        UPDATE fixed_expenses
        SET active = 0
        WHERE name = ?
          AND COALESCE(subcategory, '') = COALESCE(?, '')
          AND active = 1
        """,
        (name, subcategory),
    )

    conn.execute(
        """
        INSERT INTO fixed_expenses (name, amount, due_day, category, subcategory)
        VALUES (?, ?, ?, 'Fixed', ?)
        """,
        (name, amount, due_day, subcategory),
    )

    conn.commit()
    conn.close()


def deactivate_fixed_expense(expense_id: int) -> None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE fixed_expenses
        SET active = 0
        WHERE id = ?
        """,
        (expense_id,),
    )
    conn.commit()
    conn.close()


def get_income_sources():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, name, amount, due_day, subcategory, active
        FROM income_sources
        WHERE active = 1
        ORDER BY due_day
        """
    ).fetchall()
    conn.close()
    return rows


def upsert_income_source(name, amount, due_day, subcategory):
    conn = get_connection()

    conn.execute(
        """
        UPDATE income_sources
        SET active = 0
        WHERE name = ?
          AND COALESCE(subcategory, '') = COALESCE(?, '')
          AND active = 1
        """,
        (name, subcategory),
    )

    conn.execute(
        """
        INSERT INTO income_sources (name, amount, due_day, category, subcategory)
        VALUES (?, ?, ?, 'Income', ?)
        """,
        (name, amount, due_day, subcategory),
    )

    conn.commit()
    conn.close()


def deactivate_income_source(income_id: int) -> None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE income_sources
        SET active = 0
        WHERE id = ?
        """,
        (income_id,),
    )
    conn.commit()
    conn.close()


def upsert_objective(category: str, percentage: float):
    conn = get_connection()

    # deactivate previous active objective for this category
    conn.execute(
        """
        UPDATE budget_objectives
        SET active = 0
        WHERE category = ?
          AND active = 1
        """,
        (category,),
    )

    # insert new active objective
    conn.execute(
        """
        INSERT INTO budget_objectives (category, percentage, active)
        VALUES (?, ?, 1)
        """,
        (category, percentage),
    )

    conn.commit()
    conn.close()


def has_fixed_expenses() -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM fixed_expenses WHERE active = 1 LIMIT 1"
    ).fetchone()
    conn.close()
    return row is not None


def has_objectives() -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM budget_objectives WHERE active = 1 LIMIT 1"
    ).fetchone()
    conn.close()
    return row is not None


def has_income_sources() -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM income_sources WHERE active = 1 LIMIT 1"
    ).fetchone()
    conn.close()
    return row is not None


def preview_fixed_expenses_for_month(month_id: str):
    """
    Returns a list of dicts with:
    - date
    - name
    - category
    - subcategory
    - amount (negative)
    """
    year, month = map(int, month_id.split("-"))
    expenses = get_fixed_expenses()

    preview = []
    total = 0.0

    for fx in expenses:
        due_day = fx["due_day"]

        # Clamp day to last day of month (safety)
        try:
            tx_date = date(year, month, due_day)
        except ValueError:
            # e.g. Feb 30 → Feb 28
            last_day = (date(year, month, 1) + relativedelta(months=1, days=-1)).day
            tx_date = date(year, month, last_day)

        amount = -fx["amount"]  # expenses are negative
        total += amount

        preview.append(
            {
                "date": tx_date,
                "name": fx["name"],
                "subcategory": fx["subcategory"],
                "amount": amount,
            }
        )

    return preview, total


def preview_income_for_month(month_id: str):
    """
    Returns a list of dicts with:
    - date
    - name
    - subcategory
    - amount (positive)
    """
    year, month = map(int, month_id.split("-"))
    incomes = get_income_sources()

    preview = []
    total = 0.0

    for inc in incomes:
        due_day = inc["due_day"]

        # Clamp day to last day of month (safety)
        try:
            tx_date = date(year, month, due_day)
        except ValueError:
            last_day = (date(year, month, 1) + relativedelta(months=1, days=-1)).day
            tx_date = date(year, month, last_day)

        amount = abs(inc["amount"])
        total += amount

        preview.append(
            {
                "date": tx_date,
                "name": inc["name"],
                "subcategory": inc["subcategory"],
                "amount": amount,
            }
        )

    return preview, total


def get_transactions_for_month(month_id: str):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            date,
            category,
            subcategory,
            amount,
            payment_method,
            note
        FROM transactions
        WHERE month_id = ?
        ORDER BY date, category, subcategory
        """,
        (month_id,),
    ).fetchall()
    conn.close()
    return rows


def get_variable_by_payment_method(month_id: str) -> dict[str, float]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT payment_method, ABS(SUM(amount)) AS total
        FROM transactions
        WHERE month_id = ?
          AND category = 'Variable'
        GROUP BY payment_method
        """,
        (month_id,),
    ).fetchall()
    conn.close()

    return {r["payment_method"]: r["total"] for r in rows}


def get_oldest_open_month() -> str | None:
    conn = get_connection()
    row = conn.execute(
        """
        SELECT month_id
        FROM months
        WHERE status = 'open'
        ORDER BY month_id ASC
        LIMIT 1
        """
    ).fetchone()
    conn.close()
    return row["month_id"] if row else None
