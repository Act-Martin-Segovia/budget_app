import sqlite3
import tempfile
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


def clamp_day(year: int, month: int, day: int) -> int:
    last_day = (date(year, month, 1) + relativedelta(months=1, days=-1)).day
    return min(day, last_day)


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


def get_previous_month_id(month_id: str) -> str:
    year, month = map(int, month_id.split("-"))
    dt = date(year, month, 1) - relativedelta(months=1)
    return f"{dt.year}-{dt.month:02d}"


def compute_credit_card_cycle(
    tx_date: date, statement_close_day: int, due_day: int
) -> tuple[str, str, date]:
    """
    Returns (statement_month_id, due_month_id, due_date).
    Assumes due month is the month after the statement month.
    """
    close_day = clamp_day(tx_date.year, tx_date.month, statement_close_day)
    if tx_date.day > close_day:
        stmt_month_date = tx_date + relativedelta(months=1)
    else:
        stmt_month_date = tx_date

    statement_month_id = month_id_from_date(stmt_month_date)

    due_month_date = date(stmt_month_date.year, stmt_month_date.month, 1) + relativedelta(
        months=1
    )
    due_day_clamped = clamp_day(due_month_date.year, due_month_date.month, due_day)
    due_date = date(due_month_date.year, due_month_date.month, due_day_clamped)
    due_month_id = month_id_from_date(due_date)

    return statement_month_id, due_month_id, due_date


# ======================================================
# Bank Accounts & Credit Cards (Master Data)
# ======================================================


def get_bank_accounts() -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, name, active, effective_from_month_id, effective_to_month_id
        FROM bank_accounts
        ORDER BY name
        """
    ).fetchall()
    conn.close()
    return rows


def get_active_bank_accounts_for_month(month_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, name, effective_from_month_id, effective_to_month_id
        FROM bank_accounts
        WHERE active = 1
          AND effective_from_month_id <= ?
          AND (effective_to_month_id IS NULL OR effective_to_month_id >= ?)
        ORDER BY name
        """,
        (month_id, month_id),
    ).fetchall()
    conn.close()
    return rows


def has_bank_accounts() -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM bank_accounts WHERE active = 1 LIMIT 1"
    ).fetchone()
    conn.close()
    return row is not None


def create_bank_account(
    name: str,
    effective_from_month_id: str,
    effective_to_month_id: str | None,
    active: int = 1,
) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO bank_accounts (name, active, effective_from_month_id, effective_to_month_id)
        VALUES (?, ?, ?, ?)
        """,
        (name, active, effective_from_month_id, effective_to_month_id),
    )
    conn.commit()
    conn.close()


def update_bank_account(
    account_id: int,
    name: str,
    effective_from_month_id: str,
    effective_to_month_id: str | None,
    active: int = 1,
) -> None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE bank_accounts
        SET name = ?, active = ?, effective_from_month_id = ?, effective_to_month_id = ?
        WHERE id = ?
        """,
        (name, active, effective_from_month_id, effective_to_month_id, account_id),
    )
    conn.commit()
    conn.close()


def deactivate_bank_account(account_id: int) -> None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE bank_accounts
        SET active = 0
        WHERE id = ?
        """,
        (account_id,),
    )
    conn.commit()
    conn.close()


def get_credit_cards() -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            id,
            name,
            bank_account_id,
            statement_close_day,
            due_day,
            active,
            effective_from_month_id,
            effective_to_month_id
        FROM credit_cards
        ORDER BY name
        """
    ).fetchall()
    conn.close()
    return rows


def get_active_credit_cards_for_month(month_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            c.id,
            c.name,
            c.bank_account_id,
            c.statement_close_day,
            c.due_day,
            b.name AS bank_account_name
        FROM credit_cards c
        JOIN bank_accounts b ON b.id = c.bank_account_id
        WHERE c.active = 1
          AND b.active = 1
          AND c.effective_from_month_id <= ?
          AND (c.effective_to_month_id IS NULL OR c.effective_to_month_id >= ?)
          AND b.effective_from_month_id <= ?
          AND (b.effective_to_month_id IS NULL OR b.effective_to_month_id >= ?)
        ORDER BY c.name
        """,
        (month_id, month_id, month_id, month_id),
    ).fetchall()
    conn.close()
    return rows


def create_credit_card(
    name: str,
    bank_account_id: int,
    statement_close_day: int,
    due_day: int,
    effective_from_month_id: str,
    effective_to_month_id: str | None,
    active: int = 1,
) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO credit_cards (
            name,
            bank_account_id,
            statement_close_day,
            due_day,
            active,
            effective_from_month_id,
            effective_to_month_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            bank_account_id,
            statement_close_day,
            due_day,
            active,
            effective_from_month_id,
            effective_to_month_id,
        ),
    )
    conn.commit()
    conn.close()


def update_credit_card(
    card_id: int,
    name: str,
    bank_account_id: int,
    statement_close_day: int,
    due_day: int,
    effective_from_month_id: str,
    effective_to_month_id: str | None,
    active: int = 1,
) -> None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE credit_cards
        SET name = ?, bank_account_id = ?, statement_close_day = ?, due_day = ?,
            active = ?, effective_from_month_id = ?, effective_to_month_id = ?
        WHERE id = ?
        """,
        (
            name,
            bank_account_id,
            statement_close_day,
            due_day,
            active,
            effective_from_month_id,
            effective_to_month_id,
            card_id,
        ),
    )
    conn.commit()
    conn.close()


def deactivate_credit_card(card_id: int) -> None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE credit_cards
        SET active = 0
        WHERE id = ?
        """,
        (card_id,),
    )
    conn.commit()
    conn.close()


# ======================================================
# Account Balances & Coverage
# ======================================================


def get_account_month_balances(month_id: str) -> dict[int, dict[str, float | None]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT bank_account_id, starting_balance, ending_balance
        FROM account_month_balances
        WHERE month_id = ?
        """,
        (month_id,),
    ).fetchall()
    conn.close()
    return {
        r["bank_account_id"]: {
            "starting_balance": r["starting_balance"],
            "ending_balance": r["ending_balance"],
        }
        for r in rows
    }


def get_account_ending_balances(month_id: str) -> dict[int, float]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT bank_account_id, COALESCE(ending_balance, starting_balance) AS balance
        FROM account_month_balances
        WHERE month_id = ?
        """,
        (month_id,),
    ).fetchall()
    conn.close()
    return {r["bank_account_id"]: r["balance"] for r in rows}


def set_account_month_balances(
    month_id: str, balances: dict[int, float]
) -> None:
    conn = get_connection()
    rows = [(month_id, acct_id, bal) for acct_id, bal in balances.items()]
    conn.executemany(
        """
        INSERT INTO account_month_balances (month_id, bank_account_id, starting_balance)
        VALUES (?, ?, ?)
        ON CONFLICT(month_id, bank_account_id)
        DO UPDATE SET starting_balance = excluded.starting_balance
        """,
        rows,
    )
    conn.commit()
    conn.close()


def get_account_coverage_snapshot(month_id: str) -> list[dict[str, float | str | int]]:
    accounts = get_active_bank_accounts_for_month(month_id)
    if not accounts:
        return []

    balances = get_account_month_balances(month_id)

    conn = get_connection()
    cash_rows = conn.execute(
        """
        SELECT bank_account_id, COALESCE(SUM(amount), 0) AS net
        FROM transactions
        WHERE month_id = ?
          AND bank_account_id IS NOT NULL
        GROUP BY bank_account_id
        """,
        (month_id,),
    ).fetchall()

    card_rows = conn.execute(
        """
        SELECT c.bank_account_id, COALESCE(SUM(t.amount), 0) AS net
        FROM transactions t
        JOIN credit_cards c ON c.id = t.credit_card_id
        WHERE COALESCE(t.due_month_id, t.month_id) = ?
        GROUP BY c.bank_account_id
        """,
        (month_id,),
    ).fetchall()
    conn.close()

    cash_net = {r["bank_account_id"]: r["net"] for r in cash_rows}
    card_net = {r["bank_account_id"]: r["net"] for r in card_rows}

    snapshot: list[dict[str, float | str | int]] = []
    for acct in accounts:
        acct_id = acct["id"]
        starting = balances.get(acct_id, {}).get("starting_balance", 0.0) or 0.0
        projected = starting + cash_net.get(acct_id, 0.0)
        due = max(0.0, -(card_net.get(acct_id, 0.0)))
        shortfall = max(0.0, due - projected)
        snapshot.append(
            {
                "bank_account_id": acct_id,
                "bank_account_name": acct["name"],
                "projected_balance": projected,
                "card_due": due,
                "shortfall": shortfall,
            }
        )

    return snapshot


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
        SELECT id, name, amount, due_day, subcategory, bank_account_id, active
        FROM fixed_expenses
        WHERE active = 1
        ORDER BY due_day
        """
    ).fetchall()
    conn.close()
    return rows


def upsert_fixed_expense(name, amount, due_day, subcategory, bank_account_id):
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
        INSERT INTO fixed_expenses (
            name, amount, due_day, category, subcategory, bank_account_id
        )
        VALUES (?, ?, ?, 'Fixed', ?, ?)
        """,
        (name, amount, due_day, subcategory, bank_account_id),
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
        SELECT id, name, amount, due_day, subcategory, bank_account_id, active
        FROM income_sources
        WHERE active = 1
        ORDER BY due_day
        """
    ).fetchall()
    conn.close()
    return rows


def upsert_income_source(name, amount, due_day, subcategory, bank_account_id):
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
        INSERT INTO income_sources (
            name, amount, due_day, category, subcategory, bank_account_id
        )
        VALUES (?, ?, ?, 'Income', ?, ?)
        """,
        (name, amount, due_day, subcategory, bank_account_id),
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
            bank_account_id,
            credit_card_id,
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


def get_half_month_cashflow_splits(month_id: str) -> dict[str, dict[str, float]]:
    """
    Return totals split by half-month.

    - Income uses raw SUM(amount) (positive values).
    - Fixed/Variable/Savings use ABS(SUM(amount)) to match display conventions.
    - Uses cashflow timing: credit card charges are assigned to due_date.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            category,
            date AS effective_date,
            amount,
            payment_method,
            due_date
        FROM transactions
        WHERE month_id = ?
          AND (payment_method IS NULL OR payment_method = 'debit')
          AND category IN ('Income', 'Fixed', 'Variable', 'Savings')

        UNION ALL

        SELECT
            category,
            COALESCE(due_date, date) AS effective_date,
            amount,
            payment_method,
            due_date
        FROM transactions
        WHERE COALESCE(due_month_id, month_id) = ?
          AND payment_method = 'credit_card'
          AND category IN ('Income', 'Fixed', 'Variable', 'Savings')
        """,
        (month_id, month_id),
    ).fetchall()
    conn.close()

    splits: dict[str, dict[str, float]] = {
        "Income": {"first": 0.0, "second": 0.0},
        "Fixed": {"first": 0.0, "second": 0.0},
        "Variable": {"first": 0.0, "second": 0.0},
        "Savings": {"first": 0.0, "second": 0.0},
    }

    for row in rows:
        if not row["effective_date"]:
            continue
        day = int(str(row["effective_date"])[8:10])
        half = "first" if day <= 15 else "second"

        if row["category"] == "Income":
            splits["Income"][half] += row["amount"]
        else:
            splits[row["category"]][half] += abs(row["amount"])

    return splits


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


def is_valid_sqlite_db(file_bytes: bytes) -> bool:
    try:
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            conn = sqlite3.connect(tmp.name)
            conn.execute("SELECT name FROM sqlite_master LIMIT 1;")
            conn.close()
        return True
    except Exception:
        return False
