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


def _get_table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return {row["name"] for row in rows}


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    cols = _get_table_columns(conn, table)
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition};")


def migrate_db() -> None:
    """
    Lightweight migration for existing DBs.
    Adds new tables/columns/indexes without touching existing data.
    """
    conn = get_connection()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS bank_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            effective_from_month_id TEXT NOT NULL,
            effective_to_month_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS credit_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bank_account_id INTEGER NOT NULL,
            statement_close_day INTEGER,
            due_day INTEGER,
            active INTEGER NOT NULL DEFAULT 1,
            effective_from_month_id TEXT NOT NULL,
            effective_to_month_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bank_account_id) REFERENCES bank_accounts (id)
        );

        CREATE TABLE IF NOT EXISTS account_month_balances (
            month_id TEXT NOT NULL,
            bank_account_id INTEGER NOT NULL,
            starting_balance REAL NOT NULL,
            ending_balance REAL,
            PRIMARY KEY (month_id, bank_account_id),
            FOREIGN KEY (month_id) REFERENCES months (month_id),
            FOREIGN KEY (bank_account_id) REFERENCES bank_accounts (id)
        );
        """
    )

    _ensure_column(
        conn,
        "transactions",
        "bank_account_id",
        "bank_account_id INTEGER",
    )
    _ensure_column(
        conn,
        "transactions",
        "credit_card_id",
        "credit_card_id INTEGER",
    )
    _ensure_column(
        conn,
        "transactions",
        "statement_month_id",
        "statement_month_id TEXT",
    )
    _ensure_column(
        conn,
        "transactions",
        "due_month_id",
        "due_month_id TEXT",
    )
    _ensure_column(
        conn,
        "transactions",
        "due_date",
        "due_date TEXT",
    )
    _ensure_column(
        conn,
        "fixed_expenses",
        "bank_account_id",
        "bank_account_id INTEGER",
    )
    _ensure_column(
        conn,
        "income_sources",
        "bank_account_id",
        "bank_account_id INTEGER",
    )

    _ensure_column(
        conn,
        "credit_cards",
        "statement_close_day",
        "statement_close_day INTEGER",
    )
    _ensure_column(
        conn,
        "credit_cards",
        "due_day",
        "due_day INTEGER",
    )

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_transactions_bank_account
        ON transactions (bank_account_id);

        CREATE INDEX IF NOT EXISTS idx_transactions_credit_card
        ON transactions (credit_card_id);
        """
    )

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
        SELECT name, amount, due_day, category, subcategory, bank_account_id
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
        SELECT name, amount, due_day, category, subcategory, bank_account_id
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
    bank_account_id: Optional[int] = None,
    credit_card_id: Optional[int] = None,
    statement_month_id: Optional[str] = None,
    due_month_id: Optional[str] = None,
    due_date: Optional[str] = None,
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
            date,
            month_id,
            amount,
            category,
            subcategory,
            payment_method,
            bank_account_id,
            credit_card_id,
            statement_month_id,
            due_month_id,
            due_date,
            note,
            type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            date,
            month_id,
            amount,
            category,
            subcategory,
            payment_method,
            bank_account_id,
            credit_card_id,
            statement_month_id,
            due_month_id,
            due_date,
            note,
            tx_type,
        ),
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
            bank_account_id=fx["bank_account_id"],
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
            bank_account_id=inc["bank_account_id"],
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

    # Update per-account ending balances (cash-only, excludes credit card charges)
    acct_rows = conn.execute(
        """
        SELECT bank_account_id, starting_balance
        FROM account_month_balances
        WHERE month_id = ?
        """,
        (month_id,),
    ).fetchall()

    for acct in acct_rows:
        net = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS net
            FROM transactions
            WHERE month_id = ?
              AND bank_account_id = ?
            """,
            (month_id, acct["bank_account_id"]),
        ).fetchone()["net"]

        ending = acct["starting_balance"] + net
        conn.execute(
            """
            UPDATE account_month_balances
            SET ending_balance = ?
            WHERE month_id = ? AND bank_account_id = ?
            """,
            (ending, month_id, acct["bank_account_id"]),
        )

    conn.commit()
    conn.close()

    return ending_balance
