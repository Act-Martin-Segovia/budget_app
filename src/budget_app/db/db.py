import sqlite3
from datetime import date
import calendar
from pathlib import Path
from typing import Optional

from budget_app.utils import get_repo_root


BASE_DIR = get_repo_root()
DB_PATH = Path("db/budget.db")
SCHEMA_PATH = BASE_DIR / "src" / "budget_app" / "sql" / "schema.sql"

# -----------------------
# Connection & init
# -----------------------

def set_db_path(db_path: str | Path) -> None:
    global DB_PATH
    DB_PATH = Path(db_path)


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    if db_path is not None:
        set_db_path(db_path)
    conn = get_connection()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


# -----------------------
# Month helpers
# -----------------------

def is_month_closed(month_id: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "SELECT status FROM months WHERE month_id = ?", (month_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row is not None and row["status"] == "closed"


def month_exists(month_id: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "SELECT 1 FROM months WHERE month_id = ?", (month_id,)
    )
    exists = cur.fetchone() is not None
    conn.close()
    return exists


# -----------------------
# Fixed expenses
# -----------------------

def get_active_fixed_expenses() -> list[sqlite3.Row]:
    conn = get_connection()
    cur = conn.execute(
        """
        SELECT name, amount, due_day, category, subcategory
        FROM fixed_expenses
        WHERE active = 1
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_active_income_sources() -> list[sqlite3.Row]:
    conn = get_connection()
    cur = conn.execute(
        """
        SELECT name, amount, due_day, category, subcategory
        FROM income_sources
        WHERE active = 1
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def compute_transaction_date(month_id: str, due_day: int) -> str:
    year, month = map(int, month_id.split("-"))
    last_day = (
        date(year, month + 1, 1) - date.resolution
        if month < 12
        else date(year, 12, 31)
    ).day

    day = min(due_day, last_day)
    return f"{year}-{month:02d}-{day:02d}"

# -----------------------
# Transactions
# -----------------------

def add_transaction(
    *,
    date: str,
    month_id: str,
    amount: float,
    category: str,
    subcategory: Optional[str],
    payment_method: str = "debit",
    note: str = "",
    tx_type: str = "normal",
) -> None:
    if is_month_closed(month_id):
        raise RuntimeError(
            f"Month {month_id} is closed. Add a correction to the current month."
        )

    conn = get_connection()
    conn.execute(
        """
        INSERT INTO transactions (
            date, month_id, amount, category, subcategory, payment_method, note, type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (date, month_id, amount, category, subcategory, payment_method, note, tx_type),
    )
    conn.commit()
    conn.close()


# -----------------------
# Month lifecycle
# -----------------------

def open_month(month_id: str, starting_balance: float) -> None:
    """
    Initialize a month and materialize all active fixed expenses
    as immutable transactions for that month.
    """
    if month_exists(month_id):
        return

    conn = get_connection()
    conn.execute(
        """
        INSERT INTO months (month_id, starting_balance, status)
        VALUES (?, ?, 'open')
        """,
        (month_id, starting_balance),
    )
    conn.commit()
    conn.close()

    # Materialize fixed expenses as transactions
    for fx in get_active_fixed_expenses():
        tx_date = compute_transaction_date(month_id, fx["due_day"])

        add_transaction(
            date=tx_date,
            month_id=month_id,
            amount=-abs(fx["amount"]),
            category=fx["category"],
            subcategory=fx["subcategory"],
            note=f"Fixed expense: {fx['name']}",
            tx_type="normal",
        )

    # Materialize income sources as transactions
    for inc in get_active_income_sources():
        tx_date = compute_transaction_date(month_id, inc["due_day"])

        add_transaction(
            date=tx_date,
            month_id=month_id,
            amount=abs(inc["amount"]),
            category="Income",
            subcategory=inc["subcategory"],
            note=f"Income: {inc['name']}",
            tx_type="normal",
        )


def close_month(month_id: str) -> float:
    conn = get_connection()

    cur = conn.execute(
        """
        SELECT starting_balance
        FROM months
        WHERE month_id = ? AND status = 'open'
        """,
        (month_id,),
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise RuntimeError(f"Month {month_id} does not exist or is already closed.")

    starting_balance = row["starting_balance"]

    cur = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS net
        FROM transactions
        WHERE month_id = ?
        """,
        (month_id,),
    )
    net = cur.fetchone()["net"]

    ending_balance = starting_balance + net

    conn.execute(
        """
        UPDATE months
        SET ending_balance = ?, status = 'closed'
        WHERE month_id = ?
        """,
        (ending_balance, month_id),
    )

    conn.commit()
    conn.close()

    return ending_balance
