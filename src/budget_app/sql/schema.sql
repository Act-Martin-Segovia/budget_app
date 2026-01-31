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
    note TEXT,
    type TEXT NOT NULL CHECK (type IN ('normal', 'correction')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (month_id) REFERENCES months (month_id)
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
    active INTEGER NOT NULL DEFAULT 1,  -- 1 = active, 0 = inactive
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
