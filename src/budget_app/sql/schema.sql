-- =========================
-- Months
-- =========================
CREATE TABLE IF NOT EXISTS months (
    month_id TEXT PRIMARY KEY,          -- e.g. "2026-02"
    starting_balance REAL NOT NULL,
    ending_balance REAL,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- Bank Accounts (Master Data)
-- =========================
CREATE TABLE IF NOT EXISTS bank_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    effective_from_month_id TEXT NOT NULL,
    effective_to_month_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- Credit Cards (Master Data)
-- =========================
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

-- =========================
-- Account Balances (Per Month)
-- =========================
CREATE TABLE IF NOT EXISTS account_month_balances (
    month_id TEXT NOT NULL,
    bank_account_id INTEGER NOT NULL,
    starting_balance REAL NOT NULL,
    ending_balance REAL,

    PRIMARY KEY (month_id, bank_account_id),
    FOREIGN KEY (month_id) REFERENCES months (month_id),
    FOREIGN KEY (bank_account_id) REFERENCES bank_accounts (id)
);

-- =========================
-- Transactions
-- =========================
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,                  -- ISO date YYYY-MM-DD
    month_id TEXT NOT NULL,
    amount REAL NOT NULL,                -- +income / -expense
    category TEXT NOT NULL,              -- Fixed, Variable, Income, Savings
    subcategory TEXT,                    -- Groceries, Rent, Salary, etc.
    payment_method TEXT,
    bank_account_id INTEGER,
    credit_card_id INTEGER,
    statement_month_id TEXT,
    due_month_id TEXT,
    due_date TEXT,
    note TEXT,
    type TEXT NOT NULL CHECK (type IN ('normal', 'correction')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (month_id) REFERENCES months (month_id),
    FOREIGN KEY (bank_account_id) REFERENCES bank_accounts (id),
    FOREIGN KEY (credit_card_id) REFERENCES credit_cards (id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_month
ON transactions (month_id);


-- =========================
-- Budget Objectives (Settings)
-- =========================
CREATE TABLE IF NOT EXISTS budget_objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    subcategory TEXT,                    -- NULL = category-level objective
    percentage REAL NOT NULL CHECK (percentage >= 0),
    active INTEGER NOT NULL DEFAULT 1,   -- 1 = active, 0 = inactive
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_active_objectives
ON budget_objectives (category, subcategory)
WHERE active = 1;

-- =========================
-- Fixed Expenses (Configuration)
-- =========================
CREATE TABLE IF NOT EXISTS fixed_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                 -- e.g. "Rent"
    amount REAL NOT NULL,               -- positive number
    due_day INTEGER NOT NULL CHECK (due_day BETWEEN 1 AND 31),
    category TEXT NOT NULL DEFAULT 'Fixed',
    subcategory TEXT,                   -- Housing, Transport, Taxes, etc.
    bank_account_id INTEGER,
    active INTEGER NOT NULL DEFAULT 1,  -- 1 = active, 0 = inactive
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (bank_account_id) REFERENCES bank_accounts (id)
);

-- =========================
-- Income Sources (Configuration)
-- =========================
CREATE TABLE IF NOT EXISTS income_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                 -- e.g. "Salary"
    amount REAL NOT NULL,               -- positive number
    due_day INTEGER NOT NULL CHECK (due_day BETWEEN 1 AND 31),
    category TEXT NOT NULL DEFAULT 'Income',
    subcategory TEXT,                   -- Job, Freelance, Interest, etc.
    bank_account_id INTEGER,
    active INTEGER NOT NULL DEFAULT 1,  -- 1 = active, 0 = inactive
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (bank_account_id) REFERENCES bank_accounts (id)
);
