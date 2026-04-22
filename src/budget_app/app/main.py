import sys
import json
from pathlib import Path
from datetime import date
from html import escape
from collections.abc import Mapping

import altair as alt
import streamlit as st
import bcrypt

ROOT = Path(__file__).resolve()
while not (ROOT / ".git").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from budget_app.db.db import (
    add_savings_funded_expense,
    add_savings_movement,
    add_transaction,
    close_month,
    init_db,
    migrate_db,
    open_month,
    month_exists,
)

from budget_app.app.helper_functions import (
    current_month_id,
    list_known_months,
    get_month_snapshot,
    get_month_status,
    get_previous_month_id,
    get_month_totals_by_category,
    get_total_income,
    get_active_objectives,
    get_category_actual,
    get_category_planned,
    get_known_subcategories,
    generate_month_options,
    get_bank_accounts,
    get_active_bank_accounts_for_month,
    has_bank_accounts,
    create_bank_account,
    update_bank_account,
    deactivate_bank_account,
    get_credit_cards,
    get_active_credit_cards_for_month,
    get_active_savings_accounts_for_month,
    create_credit_card,
    create_savings_account,
    update_credit_card,
    update_savings_account,
    deactivate_credit_card,
    deactivate_savings_account,
    get_account_ending_balances,
    set_account_month_balances,
    get_credit_card_spending_summary,
    get_credit_card_spending_by_subcategory,
    get_fixed_expenses,
    upsert_fixed_expense,
    deactivate_fixed_expense,
    get_income_sources,
    upsert_income_source,
    deactivate_income_source,
    upsert_objective,
    get_savings_accounts,
    get_current_savings_balances,
    get_monthly_savings_contributions,
    has_fixed_expenses,
    has_income_sources,
    has_objectives,
    preview_fixed_expenses_for_month,
    preview_income_for_month,
    get_transactions_for_month,
    get_variable_by_payment_method,
    get_subcategory_totals_by_category,
    get_oldest_open_month,
    is_valid_sqlite_db,
)
from budget_app.utils.billing import compute_credit_card_cycle

# ======================================================
# App start
# ======================================================
ASSETS = ROOT / "src" / "assets"
st.set_page_config(
    page_title="Sobio Budget Planner",
    page_icon=str(ASSETS / "logo2.png"),
    layout="wide",
)

st.markdown(
    """
    <style>


    .page-header {
        font-size: 4.2rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        line-height: 1.05;
        margin-bottom: 0.15rem;

        background: linear-gradient(
            90deg,
            #f9fafb 0%,
            #d1d5db 30%,
            #fde68a 55%,
            #f59e0b 75%,
            #b45309 100%
        );
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 2px 8px rgba(250, 204, 21, 0.15);
    }

    .page-subtitle {
        font-size: 1.5rem;
        font-weight: 500;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: #9ca3af;
        margin-top: 0; 
    }

    .section-header {
        font-size: 2.2rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        color: #e5e7eb;
        margin: 1.6rem 0 0.8rem 0;
    }

    .subsection-header {
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: 0.01em;
        text-transform: uppercase;
        color: #e5e7eb;
        margin: 1.6rem 0 0.8rem 0;
    }

    .panel-header {
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: #cbd5e1;
        margin: 0.4rem 0 0.75rem 0;
    }

    .alloc-row {
        background: linear-gradient(135deg, #111827, #0f172a);
        border-radius: 12px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.75rem;
        border-left: 5px solid var(--accent);
    }

    .alloc-fixed { --accent: #6b7280; }

    .alloc-grid {
        display: grid;
        grid-template-columns: 1.4fr 1fr 1fr 1fr;
        align-items: center;
        column-gap: 0.5rem;
    }

    .alloc-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: #e5e7eb;
    }

    .alloc-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #9ca3af;
    }

    .alloc-value {
        font-size: 1.1rem;
        font-weight: 600;
    }

    .month-header {
        font-size: 2.0rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        color: #e5e7eb;
        text-transform: uppercase;
    }

    .month-status {
        font-size: 0.75rem;
        font-weight: 600;
        margin-left: 0.6rem;
        padding: 0.15rem 0.45rem;
        border-radius: 999px;
        vertical-align: middle;
        text-transform: uppercase;
    }

    /* Status colors */
    .status-open {
        background-color: rgba(34, 197, 94, 0.15);
        color: #22c55e;
    }

    .status-closed {
        background-color: rgba(239, 68, 68, 0.15);
        color: #ef4444;
    }

    /* ---- Metric cards ---- */
    .metric-card {
        background: linear-gradient(135deg, #111827, #0f172a);
        padding: 1.2rem 1.4rem;
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.06);
        box-shadow: 0 10px 25px rgba(0,0,0,0.35);
        text-align: left;
    }

    .section-title {
        font-size: 0.95rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #cbd5e1;
        margin-bottom: 0.4rem;
    }

    .metric-card h2 {
        margin: 0;
        font-size: 1.9rem;
        font-weight: 700;
    }

    .savings-summary-card {
        background: linear-gradient(135deg, #111827, #0f172a);
        border: 1px solid rgba(253, 230, 138, 0.22);
        border-radius: 18px;
        padding: 1.2rem 1.4rem;
        box-shadow: 0 12px 30px rgba(0,0,0,0.38);
        margin-bottom: 1.4rem;
        margin-left: auto;
        margin-right: auto;
        max-width: 520px;
    }

    .savings-summary-row {
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 1rem;
        padding: 0.85rem 0;
        border-bottom: 1px solid rgba(253, 230, 138, 0.18);
    }

    .savings-summary-row:last-child {
        border-bottom: none;
    }

    .savings-account-name {
        color: #e5e7eb;
        font-size: 1.05rem;
        font-weight: 650;
    }

    .savings-account-meta {
        color: #9ca3af;
        font-size: 0.78rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-top: 0.15rem;
    }

    .savings-account-value {
        color: #fde68a;
        font-size: 1.1rem;
        font-weight: 750;
        white-space: nowrap;
    }

    .savings-total-row {
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 1rem;
        padding-top: 1rem;
        margin-top: 0.2rem;
        border-top: 2px solid rgba(253, 230, 138, 0.38);
    }

    .savings-total-label {
        color: #fef3c7;
        font-size: 1rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .savings-total-value {
        color: #22c55e;
        font-size: 1.45rem;
        font-weight: 850;
        white-space: nowrap;
    }

    /* ---- Value coloring ---- */
    .good {
        color: #22c55e; /* green */
    }

    .bad {
        color: #ef4444; /* red */
    }

    .inflow {
        color: #86efac;
    }

    .outflow {
        color: #fca5a5;
    }
    
    </style>
    """,
    unsafe_allow_html=True,
)

col1, col2 = st.columns([1, 8], vertical_alignment="center")
with col1:
    st.image(ASSETS / "logo2.png", width=120)
with col2:
    st.markdown(
        """
        <div>
            <div class="page-header">Sobio Budget Planner</div>
            <div class="page-subtitle">Track • Plan • Save</div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.write("")
st.write("")
st.write("")
def load_user_store() -> dict[str, str]:
    users: dict[str, str] = {}

    # 1. From Streamlit secrets
    try:
        if "users" in st.secrets:
            for username, record in st.secrets["users"].items():
                if isinstance(record, Mapping) and "password_hash" in record:
                    users[str(username)] = str(record["password_hash"])
    except Exception:
        pass

    # 2. Local fallback (optional)
    if not users:
        users_path = ROOT / "users.json"
        if users_path.exists():
            try:
                with open(users_path) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    users.update({str(k): str(v) for k, v in data.items()})
            except json.JSONDecodeError:
                pass

    return users


def verify_user(username: str, password: str, users: dict[str, str]) -> bool:
    stored_hash = users.get(username)
    if not stored_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except ValueError:
        return False


def is_valid_month_id(value: str) -> bool:
    try:
        year, month = map(int, value.split("-"))
        return 1 <= month <= 12 and len(value) == 7
    except ValueError:
        return False


if "user" not in st.session_state:
    login_slot = st.empty()
    with login_slot:
        st.markdown("## Sign in")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")

        if submitted:
            users = load_user_store()
            if not users:
                st.error("No users configured. Add users to st.secrets or users.json.")
            elif verify_user(username.strip(), password, users):
                st.session_state.user = username.strip()
                login_slot.empty()
                st.rerun()
            else:
                st.error("Invalid username or password.")

    st.stop()

db_path = Path("data") / f"{st.session_state.user}.db"
#init_db(db_path)

with st.sidebar:
    st.caption(f"Signed in as {st.session_state.user}")
    if db_path.exists():
        with open(db_path, "rb") as f:
            st.download_button(
                "Download data backup",
                data=f.read(),
                file_name=(
                    f"budget_app_{st.session_state.user}_"
                    f"{date.today().isoformat()}.db"
                ),
                mime="application/x-sqlite3",
            )
    if st.button("Log out"):
        st.session_state.pop("user", None)
        st.session_state.pop("db_initialized", None)
        st.rerun()

if "db_initialized" not in st.session_state:
    init_db(db_path)
    st.session_state.db_initialized = True

# Always run lightweight migrations (idempotent) to keep existing DBs updated
migrate_db()

if "pending_tx" not in st.session_state:
    st.session_state.pending_tx = None

if "objectives_saved" not in st.session_state:
    st.session_state.objectives_saved = False

if "editing_fx" not in st.session_state:
    st.session_state.editing_fx = None

if "editing_income" not in st.session_state:
    st.session_state.editing_income = None

if "editing_account" not in st.session_state:
    st.session_state.editing_account = None

if "editing_card" not in st.session_state:
    st.session_state.editing_card = None

if "editing_savings_account" not in st.session_state:
    st.session_state.editing_savings_account = None

if "confirm_close_month_for" not in st.session_state:
    st.session_state.confirm_close_month_for = None


def submit_budget_transaction(payload: dict) -> None:
    category = payload["category"]
    tx_date = payload["date"]
    month_id = payload["month_id"]
    amount = abs(float(payload["amount"]))
    subcategory = payload.get("subcategory")
    note = payload.get("note", "")

    if category == "Income":
        add_transaction(
            date=tx_date,
            month_id=month_id,
            amount=amount,
            category=category,
            subcategory=subcategory,
            payment_method=None,
            bank_account_id=payload.get("bank_account_id"),
            credit_card_id=None,
            savings_account_id=None,
            statement_month_id=None,
            due_month_id=None,
            due_date=None,
            note=note,
        )
        return

    if category == "Savings":
        tx_id = add_transaction(
            date=tx_date,
            month_id=month_id,
            amount=-amount,
            category=category,
            subcategory=subcategory,
            payment_method="debit",
            bank_account_id=payload.get("bank_account_id"),
            credit_card_id=None,
            savings_account_id=payload.get("savings_account_id"),
            statement_month_id=None,
            due_month_id=None,
            due_date=None,
            note=note,
        )
        add_savings_movement(
            date=tx_date,
            month_id=month_id,
            savings_account_id=payload["savings_account_id"],
            amount=amount,
            movement_type="contribution",
            linked_transaction_id=tx_id,
            note=note,
        )
        return

    if (
        payload.get("payment_method") == "Debit"
        and payload.get("debit_funding_source") == "Savings account"
    ):
        add_savings_funded_expense(
            date=tx_date,
            month_id=month_id,
            amount=amount,
            category=category,
            subcategory=subcategory,
            bank_account_id=payload["settlement_bank_account_id"],
            savings_account_id=payload["savings_account_id"],
            note=note,
        )
        return

    add_transaction(
        date=tx_date,
        month_id=month_id,
        amount=-amount,
        category=category,
        subcategory=subcategory,
        payment_method=payload["payment_method"].lower().replace(" ", "_"),
        bank_account_id=payload.get("bank_account_id")
        if payload.get("payment_method") == "Debit"
        else None,
        credit_card_id=payload.get("credit_card_id")
        if payload.get("payment_method") == "Credit card"
        else None,
        savings_account_id=payload.get("savings_account_id"),
        statement_month_id=payload.get("statement_month_id")
        if payload.get("payment_method") == "Credit card"
        else None,
        due_month_id=payload.get("due_month_id")
        if payload.get("payment_method") == "Credit card"
        else None,
        due_date=payload.get("due_date")
        if payload.get("payment_method") == "Credit card"
        else None,
        note=note,
    )

dashboard_tab, trx_tab, settings_tab, backup_data_tab = st.tabs(
    ["📊 Main Dashboard", "📋 Transactions", "⚙️ Settings", "💾 Restore Backup Data"]
)

# ======================================================
# MAIN DASHBOARD TAB
# ======================================================

with dashboard_tab:

    known_months = list_known_months()
    oldest_open = get_oldest_open_month()
    if oldest_open:
        default_month = oldest_open
    else:
        default_month = current_month_id()
    
    today = date.today()
    future_months = generate_month_options(today, months_ahead=6)

    month_options = sorted(set(known_months + future_months))

    default_index = (
        month_options.index(default_month)
        if default_month in month_options
        else 0
    )

    selected_month = st.selectbox(
        "Select month",
        options=month_options,
        index=default_index,
    )

    if (
        st.session_state.confirm_close_month_for is not None
        and st.session_state.confirm_close_month_for != selected_month
    ):
        st.session_state.confirm_close_month_for = None


    if not month_exists(selected_month):
        st.info("This month has not been initialized yet.")

        preview, total_fixed = preview_fixed_expenses_for_month(selected_month)
        invalid_fixed_expenses = [fx for fx in preview if fx["issue"]]
        if preview:
            st.divider()
            st.markdown("**Fixed expenses that will apply:**")

            for fx in preview:
                c1, c2, c3, c4 = st.columns([2, 4, 3, 2])
                c1.write(fx["date"].strftime("%Y-%m-%d"))
                c2.write(f"{fx['name']} ({fx['subcategory'] or '—'})")
                c3.write(fx["payment_detail"])
                c4.write(f"${fx['amount']:,.2f}")
                if fx["issue"]:
                    st.caption(f"{fx['name']}: {fx['issue']}")
        else:
            st.divider()
            st.markdown("**Fixed expenses that will apply:**")
            st.info("No fixed expenses defined yet.")
        
        st.divider()
        st.markdown("**Income sources that will apply:**")
        income_preview, _ = preview_income_for_month(selected_month)

        if income_preview:
            for inc in income_preview:
                c1, c2, c3 = st.columns([2, 4, 2])
                c1.write(inc["date"].strftime("%Y-%m-%d"))
                c2.write(f"{inc['name']} ({inc['subcategory'] or '—'})")
                c3.write(f"${inc['amount']:,.2f}")
        else:
            st.info("No income sources defined yet.")

        st.divider()
        st.markdown("**Budget objectives that will apply**")

        objectives = get_active_objectives()

        if not objectives:
            st.info("No budget objectives defined yet.")
        else:
            for category, pct in objectives.items():
                c1, c2 = st.columns([4, 2])
                c1.write(category)
                c2.write(f"{pct:.0%} of income")

        missing_setup = []

        if not has_fixed_expenses():
            missing_setup.append("fixed expenses")

        if not has_income_sources():
            missing_setup.append("income sources")

        if not has_objectives():
            missing_setup.append("budget objectives")
        
        if not has_bank_accounts():
            missing_setup.append("bank accounts")

        if missing_setup:
            st.warning(
                "Before initializing a month, please set up: "
                + ", ".join(missing_setup)
                + ".\n\nGo to the **Settings** tab to complete the setup."
            )
        elif invalid_fixed_expenses:
            st.warning(
                "Some fixed expenses cannot be initialized for this month. "
                "Update them in the **Settings** tab."
            )
            for fx in invalid_fixed_expenses:
                st.write(f"- {fx['name']}: {fx['issue']}")
        else:
            active_accounts = get_active_bank_accounts_for_month(selected_month)
            if not active_accounts:
                st.warning(
                    "No bank accounts are active for this month. "
                    "Check effective dates in Settings."
                )
            else:
                prev_month_id = get_previous_month_id(selected_month)
                prev_balances = (
                    get_account_ending_balances(prev_month_id)
                    if month_exists(prev_month_id)
                    else {}
                )

                carry_over = True
                if prev_balances:
                    carry_over = (
                        st.radio(
                            "How should prior account balances be treated?",
                            options=[
                                "Carry them over (recommended)",
                                "Start all accounts at 0",
                            ],
                            index=0,
                        )
                        == "Carry them over (recommended)"
                    )
                else:
                    st.info(
                        "No prior account balances found. "
                        "Starting balances will default to $0.00."
                    )
                    carry_over = False

                mode_key = (selected_month, "carry" if carry_over else "zero")
                if st.session_state.get("init_bal_mode") != mode_key:
                    for acct in active_accounts:
                        default_balance = (
                            prev_balances.get(acct["id"], 0.0)
                            if carry_over
                            else 0.0
                        )
                        st.session_state[
                            f"init_bal_{selected_month}_{acct['id']}"
                        ] = float(default_balance)
                    st.session_state.init_bal_mode = mode_key

                with st.form("init_month_form"):
                    st.markdown("**Starting balances per account**")
                    for acct in active_accounts:
                        key = f"init_bal_{selected_month}_{acct['id']}"
                        if key not in st.session_state:
                            default_balance = (
                                prev_balances.get(acct["id"], 0.0)
                                if carry_over
                                else 0.0
                            )
                            st.session_state[key] = float(default_balance)
                        st.number_input(
                            acct["name"],
                            step=1.0,
                            key=key,
                        )

                    submitted_init = st.form_submit_button("Initialize month")

                if submitted_init:
                    balances = {}
                    for acct in active_accounts:
                        key = f"init_bal_{selected_month}_{acct['id']}"
                        balances[acct["id"]] = float(
                            st.session_state.get(key, 0.0)
                        )

                    starting_balance = sum(balances.values())

                    open_month(
                        selected_month,
                        starting_balance=starting_balance,
                    )
                    set_account_month_balances(selected_month, balances)

                    st.success(
                        f"Month {selected_month} initialized "
                        f"with starting balance ${starting_balance:,.2f}."
                    )
                    st.rerun()
    else:
        snapshot = get_month_snapshot(selected_month)
        status = snapshot["status"]

        st.write("")
        st.markdown(
            f"""
            <div class="month-header">
                Month: {selected_month}
                <span class="month-status status-{status}">
                    {status.upper()}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        net_class = "bad" if snapshot["net"] < 0 else "good"
        ending_class = "bad" if snapshot["projected_ending"] < 0 else "good"
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="section-title">Starting balance</div>
                    <h2>$ {snapshot['starting_balance']:,.2f}</h2>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="section-title">Net Transactions</div>
                    <h2><span class="{net_class}">$ {snapshot['net']:,.2f}</span></h2>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="section-title">Projected ending</div>
                    <h2><span class="{ending_class}">$ {snapshot['projected_ending']:,.2f}</span></h2>
                </div>
                """,
                unsafe_allow_html=True,
            )
        
        st.divider()
        st.markdown(
            '<div class="section-header">Allocation overview</div>',
            unsafe_allow_html=True,
        )


        income = get_total_income(selected_month)
        totals = get_month_totals_by_category(selected_month)
        objectives = get_active_objectives()

        if income == 0:
            st.warning("No income recorded for this month.")
        else:
            if "Fixed" in objectives:
                planned_fixed = income * objectives["Fixed"]
                actual_fixed = abs(totals.get("Fixed", 0))
                delta_fixed = planned_fixed - actual_fixed
                status_class = "bad" if delta_fixed < 0 else "good"

                st.markdown(
                    f"""
                    <div class="alloc-row alloc-fixed">
                        <div class="alloc-grid">
                            <div>
                                <div class="alloc-title">Fixed expenses</div>
                            </div>
                            <div>
                                <div class="alloc-label">Planned</div>
                                <div class="alloc-value">${planned_fixed:,.2f}</div>
                            </div>
                            <div>
                                <div class="alloc-label">Actual</div>
                                <div class="alloc-value">${actual_fixed:,.2f}</div>
                            </div>
                            <div>
                                <div class="alloc-label">{'Remaining' if delta_fixed >= 0 else 'Over'}</div>
                                <div class="alloc-value {'good' if delta_fixed >= 0 else 'bad'}">
                                    ${abs(delta_fixed):,.2f}
                                </div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            
            if "Variable" in objectives:
                variable_totals = get_variable_by_payment_method(selected_month)
                planned_variable = income * objectives["Variable"]

                spent_debit = variable_totals.get("debit", 0)
                spent_credit = variable_totals.get("credit_card", 0)
                actual_variable = spent_debit + spent_credit
                delta_variable = planned_variable - actual_variable

                st.markdown(
                    f"""
                    <div class="alloc-row alloc-fixed">
                        <div class="alloc-grid">
                            <div>
                                <div class="alloc-title">Variable expenses</div>
                                <div class="alloc-label">
                                    Debit ${spent_debit:,.2f} · Credit ${spent_credit:,.2f}
                                </div>
                            </div>
                            <div>
                                <div class="alloc-label">Planned</div>
                                <div class="alloc-value">${planned_variable:,.2f}</div>
                            </div>
                            <div>
                                <div class="alloc-label">Actual</div>
                                <div class="alloc-value">${actual_variable:,.2f}</div>
                            </div>
                            <div>
                                <div class="alloc-label">{'Remaining' if delta_variable >= 0 else 'Over'}</div>
                                <div class="alloc-value {'good' if delta_variable >= 0 else 'bad'}">
                                    ${abs(delta_variable):,.2f}
                                </div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # st.markdown(
                #     '<div class="subsection-header">Variable expenses</div>',
                #     unsafe_allow_html=True,
                # )

                # hover_text = (
                #     "- **Debit:** "
                #     f"`${spent_debit:,.2f}`\n"
                #     "- **Credit card:** "
                #     f"`${spent_credit:,.2f}`\n\n"
                #     "_Credit card amounts will be paid next month. "
                #     "Make sure the cash is reserved._"
                # )

                # c1, c2, c3 = st.columns(3)
                # c1.metric("Planned", f"${planned_variable:,.2f}")
                # c2.metric("Actual", f"${actual_variable:,.2f}", help=hover_text)
                # c2.caption("ⓘ Hover for payment method details")
                # c3.metric(
                #     "Remaining" if delta_variable >= 0 else "Over",
                #     f"${abs(delta_variable):,.2f}",
                #     delta_color="inverse" if delta_variable < 0 else "normal",
                # )              
            
            if "Savings" in objectives:
                planned_savings = income * objectives["Savings"]
                actual_savings = abs(totals.get("Savings", 0))
                delta_savings = planned_savings - actual_savings

                st.markdown(
                    f"""
                    <div class="alloc-row alloc-fixed">
                        <div class="alloc-grid">
                            <div>
                                <div class="alloc-title">Savings</div>
                            </div>
                            <div>
                                <div class="alloc-label">Planned</div>
                                <div class="alloc-value">${planned_savings:,.2f}</div>
                            </div>
                            <div>
                                <div class="alloc-label">Actual</div>
                                <div class="alloc-value">${actual_savings:,.2f}</div>
                            </div>
                            <div>
                                <div class="alloc-label">{'Remaining' if delta_savings >= 0 else 'Over'}</div>
                                <div class="alloc-value {'good' if delta_savings >= 0 else 'bad'}">
                                    ${abs(delta_savings):,.2f}
                                </div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.divider()
            st.markdown(
                '<div class="subsection-header">Objective Breakdown</div>',
                unsafe_allow_html=True,
            )
            chart_categories = [
                category for category in ["Fixed", "Variable", "Savings"] if category in objectives
            ]
            breakdown = get_subcategory_totals_by_category(selected_month, chart_categories)

            objective_rows = []
            actual_rows = []
            for category in chart_categories:
                objective_pct = objectives[category]
                objective_amount = income * objective_pct
                objective_rows.append(
                    {
                        "category": category,
                        "objective_pct": objective_pct,
                        "objective_amount": objective_amount,
                    }
                )
                for item in breakdown.get(category, []):
                    amount = float(item["total"])
                    actual_rows.append(
                        {
                            "category": category,
                            "subcategory": item["subcategory"],
                            "amount": amount,
                            "pct_of_income": (amount / income) if income else 0.0,
                            "objective_amount": objective_amount,
                            "objective_pct": objective_pct,
                        }
                    )

            objective_chart = alt.Chart(alt.Data(values=objective_rows)).mark_bar(
                color="#e5e7eb",
                opacity=0.34,
                size=72,
                cornerRadiusTopLeft=6,
                cornerRadiusTopRight=6,
            ).encode(
                x=alt.X(
                    "category:N",
                    sort=chart_categories,
                    title=None,
                    axis=alt.Axis(
                        labelAngle=0,
                        labelColor="#d1d5db",
                        labelFontSize=12,
                        tickSize=0,
                        domain=False,
                    ),
                ),
                y=alt.Y(
                    "objective_pct:Q",
                    title=None,
                    axis=alt.Axis(
                        format=".0%",
                        labelColor="#9ca3af",
                        labelFontSize=11,
                        gridColor="rgba(255,255,255,0.08)",
                        tickSize=0,
                        domain=False,
                    ),
                ),
                tooltip=[
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("objective_amount:Q", title="Objective", format=",.2f"),
                    alt.Tooltip("objective_pct:Q", title="% of income", format=".1%"),
                ],
            )

            chart_layers = [objective_chart]

            if actual_rows:
                subcategory_palette = [
                    "#fef3c7",
                    "#fde68a",
                    "#fcd34d",
                    "#fbbf24",
                    "#f59e0b",
                    "#d97706",
                    "#b45309",
                    "#92400e",
                    "#facc15",
                    "#fb923c",
                ]
                actual_chart = alt.Chart(alt.Data(values=actual_rows)).mark_bar(
                    size=52,
                    cornerRadiusTopLeft=6,
                    cornerRadiusTopRight=6,
                ).encode(
                    x=alt.X("category:N", sort=chart_categories, title=None),
                    y=alt.Y("pct_of_income:Q", title=None),
                    color=alt.Color(
                        "subcategory:N",
                        title=None,
                        scale=alt.Scale(range=subcategory_palette),
                        legend=alt.Legend(
                            orient="bottom",
                            direction="horizontal",
                            labelColor="#d1d5db",
                            labelFontSize=11,
                            symbolType="circle",
                            symbolSize=90,
                            title=None,
                        ),
                    ),
                    order=alt.Order("pct_of_income:Q", sort="descending"),
                    tooltip=[
                        alt.Tooltip("category:N", title="Category"),
                        alt.Tooltip("subcategory:N", title="Subcategory"),
                        alt.Tooltip("amount:Q", title="Actual", format=",.2f"),
                        alt.Tooltip("pct_of_income:Q", title="% of income", format=".1%"),
                        alt.Tooltip("objective_amount:Q", title="Objective", format=",.2f"),
                        alt.Tooltip("objective_pct:Q", title="Objective %", format=".1%"),
                    ],
                )
                chart_layers.append(actual_chart)

            chart = alt.layer(*chart_layers).resolve_scale(
                y="shared", color="independent"
            ).properties(width=760, height=340).configure_view(strokeWidth=0)
            chart_left, chart_center, chart_right = st.columns([1, 5, 1])
            with chart_center:
                st.altair_chart(chart, use_container_width=False)
            st.caption(
                "Light bar = category objective. Colored stack = actual subcategory "
                "usage. Bars can extend above the target when the objective is exceeded."
            )

            st.divider()
            st.markdown(
                '<div class="subsection-header">Savings & Investments</div>',
                unsafe_allow_html=True,
            )
            savings_palette = [
                "#fde68a",
                "#fcd34d",
                "#fbbf24",
                "#f59e0b",
                "#d97706",
                "#b45309",
            ]

            current_balances = get_current_savings_balances()
            contribution_rows = get_monthly_savings_contributions()

            balance_col, contribution_col = st.columns([1, 1.35])
            with balance_col:
                st.markdown(
                    '<div class="panel-header">Current Balances</div>',
                    unsafe_allow_html=True,
                )
                if not current_balances:
                    st.info("No savings or investment accounts defined yet.")
                else:
                    total_savings_balance = sum(
                        float(row["balance"]) for row in current_balances
                    )
                    account_rows = []
                    for row in current_balances:
                        account_name = escape(str(row["savings_account_name"]))
                        account_type = escape(str(row["account_type"]).title())
                        institution = escape(str(row["institution"] or ""))
                        meta_parts = [
                            part for part in [institution, account_type] if part
                        ]
                        account_meta = escape(" · ".join(meta_parts))
                        account_rows.append(
                            '<div class="savings-summary-row">'
                            "<div>"
                            f'<div class="savings-account-name">{account_name}</div>'
                            f'<div class="savings-account-meta">{account_meta}</div>'
                            "</div>"
                            f'<div class="savings-account-value">$ {float(row["balance"]):,.0f}</div>'
                            "</div>"
                        )
                    account_rows_html = "".join(account_rows)
                    summary_html = (
                        '<div class="savings-summary-card">'
                        f"{account_rows_html}"
                        '<div class="savings-total-row">'
                        '<div class="savings-total-label">Total</div>'
                        f'<div class="savings-total-value">$ {total_savings_balance:,.0f}</div>'
                        "</div>"
                        "</div>"
                    )
                    st.markdown(summary_html, unsafe_allow_html=True)
                    st.caption(
                        "Balances include opening balances, contributions, and withdrawals."
                    )

            with contribution_col:
                st.markdown(
                    '<div class="panel-header">Contributions By Month</div>',
                    unsafe_allow_html=True,
                )
                if not contribution_rows:
                    st.info("No savings contributions recorded yet.")
                else:
                    contribution_chart = (
                        alt.Chart(alt.Data(values=contribution_rows))
                        .mark_bar(
                            cornerRadiusTopLeft=6,
                            cornerRadiusTopRight=6,
                            size=48,
                        )
                        .encode(
                            x=alt.X(
                                "month_id:N",
                                title=None,
                                axis=alt.Axis(
                                    labelAngle=0,
                                    labelColor="#d1d5db",
                                    labelFontSize=12,
                                    tickSize=0,
                                    domain=False,
                                ),
                            ),
                            y=alt.Y(
                                "contribution_amount:Q",
                                title=None,
                                axis=alt.Axis(
                                    format="~s",
                                    labelColor="#9ca3af",
                                    labelFontSize=11,
                                    gridColor="rgba(255,255,255,0.08)",
                                    tickSize=0,
                                    domain=False,
                                ),
                            ),
                            color=alt.Color(
                                "savings_account_name:N",
                                title=None,
                                scale=alt.Scale(range=savings_palette),
                                legend=alt.Legend(
                                    orient="bottom",
                                    direction="horizontal",
                                    labelColor="#d1d5db",
                                    labelFontSize=11,
                                    symbolType="circle",
                                    symbolSize=90,
                                    title=None,
                                ),
                            ),
                            order=alt.Order("contribution_amount:Q", sort="descending"),
                            tooltip=[
                                alt.Tooltip("month_id:N", title="Month"),
                                alt.Tooltip(
                                    "savings_account_name:N",
                                    title="Savings account",
                                ),
                                alt.Tooltip(
                                    "contribution_amount:Q",
                                    title="Contribution",
                                    format=",.2f",
                                ),
                            ],
                        )
                        .properties(width=560, height=320)
                        .configure_view(strokeWidth=0)
                        .configure_axis(labelFont="sans-serif", titleFont="sans-serif")
                    )
                    contribution_left, contribution_center, contribution_right = (
                        st.columns([1, 6, 1])
                    )
                    with contribution_center:
                        st.altair_chart(
                            contribution_chart,
                            use_container_width=False,
                        )
                    st.caption(
                        "Opening balances are excluded so backfills do not appear as monthly savings."
                    )

            st.divider()
            st.markdown(
                '<div class="subsection-header">Credit Card Details</div>',
                unsafe_allow_html=True,
            )
            credit_summary = get_credit_card_spending_summary(selected_month)
            credit_breakdown = get_credit_card_spending_by_subcategory(selected_month)

            card_summary_col, card_chart_col = st.columns([1, 1.35])
            with card_summary_col:
                st.markdown(
                    '<div class="panel-header">Current Month Spending</div>',
                    unsafe_allow_html=True,
                )
                if not credit_summary:
                    st.info("No active credit cards for this month.")
                else:
                    total_credit_spent = sum(
                        float(row["spent"]) for row in credit_summary
                    )
                    card_rows = []
                    for row in credit_summary:
                        card_name = escape(str(row["credit_card_name"]))
                        bank_name = escape(str(row["bank_account_name"]))
                        card_rows.append(
                            '<div class="savings-summary-row">'
                            "<div>"
                            f'<div class="savings-account-name">{card_name}</div>'
                            f'<div class="savings-account-meta">Paid from {bank_name}</div>'
                            "</div>"
                            f'<div class="savings-account-value">$ {float(row["spent"]):,.0f}</div>'
                            "</div>"
                        )
                    card_rows_html = "".join(card_rows)
                    card_summary_html = (
                        '<div class="savings-summary-card">'
                        f"{card_rows_html}"
                        '<div class="savings-total-row">'
                        '<div class="savings-total-label">Total</div>'
                        f'<div class="savings-total-value">$ {total_credit_spent:,.0f}</div>'
                        "</div>"
                        "</div>"
                    )
                    st.markdown(card_summary_html, unsafe_allow_html=True)
                    st.caption(
                        "Amounts include credit-card transactions recorded in this selected month."
                    )

            with card_chart_col:
                st.markdown(
                    '<div class="panel-header">Spending By Subcategory</div>',
                    unsafe_allow_html=True,
                )
                if not credit_breakdown:
                    st.info("No credit-card spending recorded this month.")
                else:
                    credit_palette = [
                        "#fef3c7",
                        "#fde68a",
                        "#fcd34d",
                        "#fbbf24",
                        "#f59e0b",
                        "#d97706",
                        "#b45309",
                        "#92400e",
                    ]
                    credit_chart = (
                        alt.Chart(alt.Data(values=credit_breakdown))
                        .mark_bar(
                            cornerRadiusTopLeft=6,
                            cornerRadiusTopRight=6,
                            size=48,
                        )
                        .encode(
                            x=alt.X(
                                "credit_card_name:N",
                                title=None,
                                axis=alt.Axis(
                                    labelAngle=0,
                                    labelColor="#d1d5db",
                                    labelFontSize=12,
                                    tickSize=0,
                                    domain=False,
                                ),
                            ),
                            y=alt.Y(
                                "spent:Q",
                                title=None,
                                axis=alt.Axis(
                                    format="~s",
                                    labelColor="#9ca3af",
                                    labelFontSize=11,
                                    gridColor="rgba(255,255,255,0.08)",
                                    tickSize=0,
                                    domain=False,
                                ),
                            ),
                            color=alt.Color(
                                "subcategory:N",
                                title=None,
                                scale=alt.Scale(range=credit_palette),
                                legend=alt.Legend(
                                    orient="bottom",
                                    direction="horizontal",
                                    labelColor="#d1d5db",
                                    labelFontSize=11,
                                    symbolType="circle",
                                    symbolSize=90,
                                    title=None,
                                ),
                            ),
                            order=alt.Order("spent:Q", sort="descending"),
                            tooltip=[
                                alt.Tooltip("credit_card_name:N", title="Credit card"),
                                alt.Tooltip("subcategory:N", title="Subcategory"),
                                alt.Tooltip("spent:Q", title="Spent", format=",.2f"),
                            ],
                        )
                        .properties(width=560, height=320)
                        .configure_view(strokeWidth=0)
                        .configure_axis(labelFont="sans-serif", titleFont="sans-serif")
                    )
                    credit_left, credit_center, credit_right = st.columns([1, 6, 1])
                    with credit_center:
                        st.altair_chart(credit_chart, use_container_width=False)

        if status == "open":
            st.divider()
            # --- First step ---
            if st.session_state.confirm_close_month_for != selected_month:
                if st.button("Close month"):
                    st.session_state.confirm_close_month_for = selected_month
                    st.rerun()

            # --- Confirmation step ---
            else:
                st.warning(
                    "⚠️ **Are you sure you want to close this month?**\n\n"
                    "Once closed, you won’t be able to modify transactions."
                )

                c1, c2 = st.columns(2)

                if c1.button("Yes, close month", type="primary"):
                    close_month(selected_month)
                    st.session_state.confirm_close_month_for = None
                    st.success("Month closed.")
                    st.rerun()

                if c2.button("Cancel"):
                    st.session_state.confirm_close_month_for = None
                    st.info("Month closure cancelled.")
                    st.rerun()

# ======================================================
# TRX DETAILS TAB
# ======================================================
with trx_tab:
    if not month_exists(selected_month):
        st.info("This month has not been initialized yet.")
    else:
        status = get_month_status(selected_month)
        # -----------------------
        # Transactions (only if open)
        # -----------------------
        if status == "open":
            st.markdown(
                '<div class="subsection-header">Transaction Form</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="alloc-label">Add new transactions for an initialized month</div>',
                unsafe_allow_html=True,
            )
            st.write("")

            accounts_for_month = get_active_bank_accounts_for_month(selected_month)
            account_label_map = {
                f"{a['name']} (id {a['id']})": a["id"] for a in accounts_for_month
            }
            account_options = ["—"] + list(account_label_map.keys())

            cards_for_month = get_active_credit_cards_for_month(selected_month)
            card_label_map = {
                f"{c['name']} → {c['bank_account_name']} (id {c['id']})": c["id"]
                for c in cards_for_month
            }
            card_options = ["—"] + list(card_label_map.keys())
            card_meta_map = {
                c["id"]: {
                    "statement_close_day": c["statement_close_day"],
                    "due_day": c["due_day"],
                }
                for c in cards_for_month
            }
            savings_accounts_for_month = get_active_savings_accounts_for_month(
                selected_month
            )
            savings_label_map = {
                (
                    f"{s['name']} · {s['account_type'].title()}"
                    + (
                        f" · linked {s['linked_bank_account_name']}"
                        if s["linked_bank_account_name"]
                        else ""
                    )
                ): s["id"]
                for s in savings_accounts_for_month
            }
            savings_options = ["—"] + list(savings_label_map.keys())
            savings_meta_map = {
                s["id"]: {
                    "linked_bank_account_id": s["linked_bank_account_id"],
                    "linked_bank_account_name": s["linked_bank_account_name"],
                }
                for s in savings_accounts_for_month
            }

            CATEGORY_LABELS = {
                "Income": "Income",
                "Variable": "Variable Expense",
                "Savings": "Savings",
            }
            known_subcategories = get_known_subcategories()

            with st.form("transaction_form", clear_on_submit=True):
                tx_date = st.date_input("Date")
                category_label = st.selectbox("Category", list(CATEGORY_LABELS.values()))
                subcategory = st.selectbox(
                    "Subcategory",
                    options=known_subcategories,
                    index=None,
                    placeholder="Select an existing subcategory or type a new one",
                    accept_new_options=True,
                )
                amount = st.number_input("Amount", min_value=0.0, step=1.0)
                payment_method = st.selectbox("Payment method", ["Debit", "Credit card"])
                debit_funding_source = st.selectbox(
                    "Debit funding source",
                    ["Bank account", "Savings account"],
                )
                bank_account_label = st.selectbox(
                    "Bank account (for income/debit)",
                    options=account_options,
                )
                credit_card_label = st.selectbox(
                    "Credit card (for credit card purchases)",
                    options=card_options,
                )
                savings_account_label = st.selectbox(
                    "Savings / investment account",
                    options=savings_options,
                )
                note = st.text_input("Note (optional)")
                submitted = st.form_submit_button("Add transaction")

            if submitted:
                category = next(
                    k for k, v in CATEGORY_LABELS.items() if v == category_label
                )
                subcategory = (subcategory or "").strip()
                selected_year, selected_month_num = map(int, selected_month.split("-"))
                if (tx_date.year, tx_date.month) != (
                    selected_year,
                    selected_month_num,
                ):
                    st.error(
                        "This transaction's date does not match the selected month."
                    )
                elif category != "Income" and not subcategory:
                    st.error("Subcategory is required.")
                elif amount <= 0:
                    st.error("Amount must be greater than zero.")
                else:
                    bank_account_id = account_label_map.get(bank_account_label)
                    credit_card_id = card_label_map.get(credit_card_label)
                    savings_account_id = savings_label_map.get(savings_account_label)
                    savings_meta = savings_meta_map.get(savings_account_id, {})
                    settlement_bank_account_id = savings_meta.get("linked_bank_account_id")
                    statement_month_id = None
                    due_month_id = None
                    due_date = None

                    is_valid = True
                    if category == "Income":
                        if bank_account_id is None:
                            st.error("Income must be assigned to a bank account.")
                            is_valid = False
                    elif category == "Savings":
                        if payment_method != "Debit":
                            st.error("Savings entries must use debit.")
                            is_valid = False
                        if bank_account_id is None:
                            st.error(
                                "Savings entries must be assigned to a bank account."
                            )
                            is_valid = False
                        if savings_account_id is None:
                            st.error(
                                "Savings entries must select a savings or investment account."
                            )
                            is_valid = False
                    else:
                        if payment_method == "Debit":
                            if debit_funding_source == "Bank account" and bank_account_id is None:
                                st.error(
                                    "Debit transactions must be assigned to a bank account."
                                )
                                is_valid = False
                            if debit_funding_source == "Savings account":
                                if savings_account_id is None:
                                    st.error(
                                        "Savings-funded debit transactions must select a savings or investment account."
                                    )
                                    is_valid = False
                                elif settlement_bank_account_id is None:
                                    linked_name = savings_meta.get("linked_bank_account_name")
                                    st.error(
                                        "The selected savings account is missing a linked bank account. "
                                        "Update it in Settings before using it as a funding source."
                                        + (f" Current linked bank: {linked_name}." if linked_name else "")
                                    )
                                    is_valid = False
                        if payment_method == "Credit card" and credit_card_id is None:
                            st.error(
                                "Credit card transactions must select a credit card."
                            )
                            is_valid = False
                        if payment_method == "Credit card" and credit_card_id is not None:
                            meta = card_meta_map.get(credit_card_id, {})
                            close_day = meta.get("statement_close_day")
                            due_day = meta.get("due_day")
                            if close_day is None or due_day is None:
                                st.error(
                                    "This credit card is missing statement close day "
                                    "or due day. Update it in Settings."
                                )
                                is_valid = False
                            else:
                                statement_month_id, due_month_id, due_date = (
                                    compute_credit_card_cycle(
                                        tx_date, int(close_day), int(due_day)
                                    )
                                )

                    if is_valid:
                        subcategory = subcategory or None

                        if category == "Income":
                            submit_budget_transaction(
                                {
                                    "date": tx_date.isoformat(),
                                    "month_id": selected_month,
                                    "amount": amount,
                                    "category": category,
                                    "subcategory": subcategory,
                                    "bank_account_id": bank_account_id,
                                    "note": note,
                                }
                            )
                            st.success("Income transaction added.")
                            st.rerun()
                        else:
                            actual = get_category_actual(selected_month, category)
                            planned = get_category_planned(selected_month, category)
                            simulated = actual + amount

                            if simulated > planned:
                                st.session_state.pending_tx = {
                                    "date": tx_date.isoformat(),
                                    "month_id": selected_month,
                                    "amount": amount,
                                    "category": category,
                                    "subcategory": subcategory,
                                    "payment_method": payment_method,
                                    "debit_funding_source": debit_funding_source,
                                    "bank_account_id": bank_account_id,
                                    "savings_account_id": savings_account_id,
                                    "settlement_bank_account_id": settlement_bank_account_id,
                                    "credit_card_id": credit_card_id,
                                    "statement_month_id": statement_month_id,
                                    "due_month_id": due_month_id,
                                    "due_date": due_date.isoformat() if due_date else None,
                                    "note": note,
                                    "planned": planned,
                                    "simulated": simulated,
                                }
                            else:
                                submit_budget_transaction(
                                    {
                                        "date": tx_date.isoformat(),
                                        "month_id": selected_month,
                                        "amount": amount,
                                        "category": category,
                                        "subcategory": subcategory,
                                        "payment_method": payment_method,
                                        "debit_funding_source": debit_funding_source,
                                        "bank_account_id": bank_account_id,
                                        "savings_account_id": savings_account_id,
                                        "settlement_bank_account_id": settlement_bank_account_id,
                                        "credit_card_id": credit_card_id,
                                        "statement_month_id": statement_month_id,
                                        "due_month_id": due_month_id,
                                        "due_date": due_date.isoformat()
                                        if due_date
                                        else None,
                                        "note": note,
                                    }
                                )
                                st.success("Transaction added.")
                                st.rerun()

            pending = st.session_state.pending_tx
            if pending:
                st.warning(
                    f"With this transaction you will exceed the target.\n\n"
                    f"Planned: ${pending['planned']:,.2f}\n"
                    f"After: ${pending['simulated']:,.2f}"
                )

                c1, c2 = st.columns(2)
                if c1.button("Cancel"):
                    st.session_state.pending_tx = None
                if c2.button("Continue anyway"):
                    submit_budget_transaction(pending)
                    st.session_state.pending_tx = None
                    st.success("Transaction added.")
                    st.rerun()
            st.divider()

        transactions = get_transactions_for_month(selected_month)

        st.subheader(f"Transaction Details — {selected_month}")
        if not transactions:
            st.info("No transactions recorded for this month yet.")
        else:
            account_name_map = {
                a["id"]: a["name"] for a in get_bank_accounts()
            }
            card_name_map = {
                c["id"]: c["name"] for c in get_credit_cards()
            }
            savings_name_map = {
                s["id"]: s["name"] for s in get_savings_accounts()
            }

            filter_col, group_col = st.columns(2)
            with filter_col:
                filter_labels = st.multiselect(
                    "Filter by category",
                    options=["Fixed", "Variable", "Savings", "Income", "Transfer"],
                    default=["Fixed", "Variable", "Savings", "Income", "Transfer"],
                )
            if filter_labels:
                transactions = [
                    tx for tx in transactions if tx["category"] in filter_labels
                ]

            if not transactions:
                st.info("No transactions match this filter.")
                st.stop()

            with group_col:
                group_labels = st.multiselect(
                    "Group by",
                    options=["Category", "Subcategory", "Payment method"],
                )

            if not group_labels:
                # Convert to display-friendly format
                table = []
                for tx in transactions:
                    table.append(
                        {
                            "Date": tx["date"],
                            "Category": tx["category"],
                            "Subcategory": tx["subcategory"] or "—",
                            "Amount": f"${tx['amount']:,.2f}",
                            "Payment method": tx["payment_method"],
                            "Bank account": account_name_map.get(
                                tx["bank_account_id"], "—"
                            ),
                            "Credit card": card_name_map.get(
                                tx["credit_card_id"], "—"
                            ),
                            "Savings account": savings_name_map.get(
                                tx["savings_account_id"], "—"
                            ),
                            "Note": tx["note"] or "",
                        }
                    )
            else:
                group_key_map = {
                    "Category": "category",
                    "Subcategory": "subcategory",
                    "Payment method": "payment_method",
                }
                group_keys = [group_key_map[label] for label in group_labels]

                grouped: dict[tuple[str, ...], dict[str, float]] = {}
                for tx in transactions:
                    key_parts = []
                    for key in group_keys:
                        value = tx[key]
                        key_parts.append(value or "—")
                    key_tuple = tuple(key_parts)
                    if key_tuple not in grouped:
                        grouped[key_tuple] = {"Total": 0.0, "Count": 0}
                    grouped[key_tuple]["Total"] += abs(tx["amount"])
                    grouped[key_tuple]["Count"] += 1

                table = []
                for key_tuple, data in sorted(
                    grouped.items(), key=lambda item: item[1]["Total"], reverse=True
                ):
                    row = {}
                    for label, value in zip(group_labels, key_tuple):
                        row[label] = value
                    row["Count"] = data["Count"]
                    row["Total (abs)"] = f"${data['Total']:,.2f}"
                    table.append(row)

            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True,
            )

# ======================================================
# SETTINGS TAB
# ======================================================

with settings_tab:
    can_delete_for_selected_month = not month_exists(selected_month)
    st.info(
        "Start here 👋\n\n"
        "1. Add your bank accounts\n"
        "2. Add your credit cards\n"
        "3. Add your savings / investment accounts\n"
        "4. Define your fixed expenses\n"
        "5. Add your income sources\n"
        "6. Set your budget objectives\n"
        "7. Then initialize your first month from the Dashboard"
    )
    if not can_delete_for_selected_month:
        st.warning(
            f"Month {selected_month} is already initialized. "
            "Fixed expenses and income sources can only be deleted "
            "before initializing the selected month."
        )

    bank_tab, card_tab, savings_tab, fixed_tab, income_tab, objectives_tab = st.tabs(
        [
            "Bank Accounts",
            "Credit Cards",
            "Savings & Investments",
            "Fixed Expenses",
            "Income",
            "Budget Objectives",
        ]
    )

    # ---------------- Bank accounts ----------------
    with bank_tab:
        st.markdown("### Bank Accounts")
        st.info(
            "Bank accounts are master data. Use effective dates to control "
            "which months they apply to."
        )

        accounts = get_bank_accounts()
        if accounts:
            for acct in accounts:
                c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 1, 1])
                c1.write(acct["name"])
                c2.write(acct["effective_from_month_id"])
                c3.write(acct["effective_to_month_id"] or "—")
                c4.write("Active" if acct["active"] else "Inactive")
                if c5.button("Edit", key=f"edit_acct_{acct['id']}"):
                    st.session_state.editing_account = dict(acct)
                if c6.button("Deactivate", key=f"deact_acct_{acct['id']}"):
                    deactivate_bank_account(acct["id"])
                    st.session_state.editing_account = None
                    st.success("Bank account deactivated.")
                    st.rerun()
        else:
            st.info("No bank accounts yet.")

        st.divider()
        st.markdown("#### Add / Edit Bank Account")

        acct = st.session_state.editing_account or {}
        with st.form("bank_account_form"):
            name = st.text_input("Name", value=acct.get("name", ""))
            effective_from = st.text_input(
                "Effective from (YYYY-MM)",
                value=acct.get("effective_from_month_id", current_month_id()),
            )
            effective_to = st.text_input(
                "Effective to (YYYY-MM, optional)",
                value=acct.get("effective_to_month_id") or "",
            )
            active = st.checkbox("Active", value=bool(acct.get("active", 1)))
            submitted = st.form_submit_button("Save")

        if submitted:
            effective_to_val = effective_to.strip() or None
            if not name:
                st.error("Name is required.")
            elif not is_valid_month_id(effective_from):
                st.error("Effective from must be in YYYY-MM format.")
            elif effective_to_val and not is_valid_month_id(effective_to_val):
                st.error("Effective to must be in YYYY-MM format.")
            elif effective_to_val and effective_to_val < effective_from:
                st.error("Effective to must be after effective from.")
            else:
                if acct.get("id"):
                    update_bank_account(
                        acct["id"],
                        name.strip(),
                        effective_from,
                        effective_to_val,
                        1 if active else 0,
                    )
                    st.session_state.editing_account = None
                    st.success("Bank account updated.")
                else:
                    create_bank_account(
                        name.strip(),
                        effective_from,
                        effective_to_val,
                        1 if active else 0,
                    )
                    st.success("Bank account created.")
                st.rerun()

    # ---------------- Credit cards ----------------
    with card_tab:
        st.markdown("### Credit Cards")
        st.info(
            "Credit cards are linked to a bank account that will pay them. "
            "Statement close day and due day are used to estimate cashflow "
            "in the following month."
        )

        accounts = get_bank_accounts()
        account_name_map = {a["id"]: a["name"] for a in accounts}
        account_label_map = {
            f"{a['name']} (id {a['id']})": a["id"] for a in accounts
        }
        account_options = list(account_label_map.keys())

        cards = get_credit_cards()
        if cards:
            for card in cards:
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([3, 2, 1.5, 1.5, 2, 2, 1, 1])
                c1.write(card["name"])
                c2.write(account_name_map.get(card["bank_account_id"], "—"))
                c3.write(card["statement_close_day"] or "—")
                c4.write(card["due_day"] or "—")
                c5.write(card["effective_from_month_id"])
                c6.write(card["effective_to_month_id"] or "—")
                if c7.button("Edit", key=f"edit_card_{card['id']}"):
                    st.session_state.editing_card = dict(card)
                if c8.button("Deactivate", key=f"deact_card_{card['id']}"):
                    deactivate_credit_card(card["id"])
                    st.session_state.editing_card = None
                    st.success("Credit card deactivated.")
                    st.rerun()
        else:
            st.info("No credit cards yet.")

        st.divider()
        st.markdown("#### Add / Edit Credit Card")

        card = st.session_state.editing_card or {}
        with st.form("credit_card_form"):
            name = st.text_input("Name", value=card.get("name", ""))
            if account_options:
                default_account = None
                if card.get("bank_account_id"):
                    for label, acct_id in account_label_map.items():
                        if acct_id == card["bank_account_id"]:
                            default_account = label
                            break
                selected_account = st.selectbox(
                    "Bank account that pays this card",
                    options=account_options,
                    index=account_options.index(default_account)
                    if default_account in account_options
                    else 0,
                    )
            else:
                selected_account = None
                st.warning("Add a bank account before creating a credit card.")

            statement_close_day = st.number_input(
                "Statement close day (1–31)",
                min_value=1,
                max_value=31,
                value=card.get("statement_close_day", 20) or 20,
            )
            due_day = st.number_input(
                "Payment due day (1–31, following month)",
                min_value=1,
                max_value=31,
                value=card.get("due_day", 5) or 5,
            )
            effective_from = st.text_input(
                "Effective from (YYYY-MM)",
                value=card.get("effective_from_month_id", current_month_id()),
            )
            effective_to = st.text_input(
                "Effective to (YYYY-MM, optional)",
                value=card.get("effective_to_month_id") or "",
            )
            active = st.checkbox("Active", value=bool(card.get("active", 1)))
            submitted = st.form_submit_button("Save")

        if submitted:
            effective_to_val = effective_to.strip() or None
            bank_account_id = (
                account_label_map.get(selected_account) if selected_account else None
            )
            if not name:
                st.error("Name is required.")
            elif bank_account_id is None:
                st.error("Select a bank account for this credit card.")
            elif not is_valid_month_id(effective_from):
                st.error("Effective from must be in YYYY-MM format.")
            elif effective_to_val and not is_valid_month_id(effective_to_val):
                st.error("Effective to must be in YYYY-MM format.")
            elif effective_to_val and effective_to_val < effective_from:
                st.error("Effective to must be after effective from.")
            else:
                if card.get("id"):
                    update_credit_card(
                        card["id"],
                        name.strip(),
                        bank_account_id,
                        int(statement_close_day),
                        int(due_day),
                        effective_from,
                        effective_to_val,
                        1 if active else 0,
                    )
                    st.session_state.editing_card = None
                    st.success("Credit card updated.")
                else:
                    create_credit_card(
                        name.strip(),
                        bank_account_id,
                        int(statement_close_day),
                        int(due_day),
                        effective_from,
                        effective_to_val,
                        1 if active else 0,
                    )
                    st.success("Credit card created.")
                st.rerun()

    # ---------------- Savings accounts ----------------
    with savings_tab:
        st.markdown("### Savings & Investment Accounts")
        st.info(
            "Use these accounts to track long-term balances and fund expenses "
            "directly from savings. Link a bank account if you want savings-funded "
            "debit expenses to create the transfer automatically."
        )

        accounts = get_bank_accounts()
        account_label_map = {
            f"{a['name']} (id {a['id']})": a["id"] for a in accounts
        }
        account_options = ["—"] + list(account_label_map.keys())

        savings_accounts = get_savings_accounts()
        if savings_accounts:
            for savings in savings_accounts:
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(
                    [2.5, 1.6, 1.6, 2.2, 1.7, 1.7, 1, 1]
                )
                c1.write(savings["name"])
                c2.write(savings["institution"] or "—")
                c3.write(str(savings["account_type"]).title())
                c4.write(savings["linked_bank_account_name"] or "—")
                c5.write(savings["effective_from_month_id"])
                c6.write(savings["effective_to_month_id"] or "—")
                if c7.button("Edit", key=f"edit_savings_{savings['id']}"):
                    st.session_state.editing_savings_account = dict(savings)
                if c8.button("Deactivate", key=f"deact_savings_{savings['id']}"):
                    deactivate_savings_account(savings["id"])
                    st.session_state.editing_savings_account = None
                    st.success("Savings account deactivated.")
                    st.rerun()
        else:
            st.info("No savings or investment accounts yet.")

        st.divider()
        st.markdown("#### Add / Edit Savings Account")

        savings = st.session_state.editing_savings_account or {}
        with st.form("savings_account_form"):
            name = st.text_input("Name", value=savings.get("name", ""))
            institution = st.text_input(
                "Institution (optional)", value=savings.get("institution", "") or ""
            )
            account_type = st.selectbox(
                "Account type",
                options=["savings", "tfsa", "rrsp", "investment", "other"],
                index=[
                    "savings",
                    "tfsa",
                    "rrsp",
                    "investment",
                    "other",
                ].index(savings.get("account_type", "savings")),
            )
            default_linked_account = None
            if savings.get("linked_bank_account_id"):
                for label, acct_id in account_label_map.items():
                    if acct_id == savings["linked_bank_account_id"]:
                        default_linked_account = label
                        break
            linked_bank_account_label = st.selectbox(
                "Linked bank account (optional)",
                options=account_options,
                index=account_options.index(default_linked_account)
                if default_linked_account in account_options
                else 0,
            )
            effective_from = st.text_input(
                "Effective from (YYYY-MM)",
                value=savings.get("effective_from_month_id", current_month_id()),
            )
            effective_to = st.text_input(
                "Effective to (YYYY-MM, optional)",
                value=savings.get("effective_to_month_id") or "",
            )
            active = st.checkbox("Active", value=bool(savings.get("active", 1)))
            submitted = st.form_submit_button("Save")

        if submitted:
            effective_to_val = effective_to.strip() or None
            linked_bank_account_id = account_label_map.get(linked_bank_account_label)
            if not name:
                st.error("Name is required.")
            elif not is_valid_month_id(effective_from):
                st.error("Effective from must be in YYYY-MM format.")
            elif effective_to_val and not is_valid_month_id(effective_to_val):
                st.error("Effective to must be in YYYY-MM format.")
            elif effective_to_val and effective_to_val < effective_from:
                st.error("Effective to must be after effective from.")
            else:
                if savings.get("id"):
                    update_savings_account(
                        savings["id"],
                        name.strip(),
                        institution.strip() or None,
                        account_type,
                        linked_bank_account_id,
                        effective_from,
                        effective_to_val,
                        1 if active else 0,
                    )
                    st.session_state.editing_savings_account = None
                    st.success("Savings account updated.")
                else:
                    create_savings_account(
                        name.strip(),
                        institution.strip() or None,
                        account_type,
                        linked_bank_account_id,
                        effective_from,
                        effective_to_val,
                        1 if active else 0,
                    )
                    st.success("Savings account created.")
                st.rerun()

        st.divider()
        st.markdown("#### Record Opening Balance")
        st.caption(
            "Use this to backfill money that existed before you started tracking "
            "this app. It affects savings balances only and does not count as "
            "monthly income or a savings contribution."
        )

        active_savings_accounts = [
            s for s in get_savings_accounts() if s["active"]
        ]
        opening_balance_label_map = {
            f"{s['name']} (id {s['id']})": s["id"] for s in active_savings_accounts
        }
        opening_balance_options = list(opening_balance_label_map.keys())
        with st.form("savings_opening_balance_form"):
            if opening_balance_options:
                opening_balance_label = st.selectbox(
                    "Savings / investment account",
                    options=opening_balance_options,
                )
            else:
                opening_balance_label = None
                st.warning("Create a savings or investment account first.")
            opening_balance_date = st.date_input("Opening balance date")
            opening_balance_amount = st.number_input(
                "Opening balance amount",
                min_value=0.0,
                step=100.0,
            )
            opening_balance_note = st.text_input(
                "Note",
                value="Opening balance before app tracking",
            )
            submitted_opening_balance = st.form_submit_button(
                "Record opening balance"
            )

        if submitted_opening_balance:
            savings_account_id = (
                opening_balance_label_map.get(opening_balance_label)
                if opening_balance_label
                else None
            )
            opening_month_id = (
                f"{opening_balance_date.year}-{opening_balance_date.month:02d}"
            )
            if savings_account_id is None:
                st.error("Select a savings or investment account.")
            elif opening_balance_amount <= 0:
                st.error("Opening balance amount must be greater than zero.")
            elif not month_exists(opening_month_id):
                st.error(
                    "The opening balance month must be initialized first. "
                    f"Initialize {opening_month_id} from the Dashboard or choose "
                    "a date in an initialized month."
                )
            else:
                add_savings_movement(
                    date=opening_balance_date.isoformat(),
                    month_id=opening_month_id,
                    savings_account_id=savings_account_id,
                    amount=opening_balance_amount,
                    movement_type="opening_balance",
                    linked_transaction_id=None,
                    note=opening_balance_note,
                )
                st.success("Opening balance recorded.")
                st.rerun()

    # ---------------- Fixed expenses ----------------
    with fixed_tab:
        st.markdown("### Fixed Expenses")
        st.info(
            "Fixed expenses apply to future months only. "
            "They are copied as transactions when a month is initialized."
        )

        accounts = get_bank_accounts()
        account_name_map = {a["id"]: a["name"] for a in accounts}
        account_label_map = {
            f"{a['name']} (id {a['id']})": a["id"] for a in accounts
        }
        account_options = ["—"] + list(account_label_map.keys())
        cards = get_credit_cards()
        card_name_map = {c["id"]: c["name"] for c in cards}
        card_label_map = {
            (
                f"{c['name']} (id {c['id']})"
                if c["active"]
                else f"{c['name']} (id {c['id']}, inactive)"
            ): c["id"]
            for c in cards
        }
        card_options = ["—"] + list(card_label_map.keys())

        expenses = get_fixed_expenses()

        for fx in expenses:
            payment_method = fx["payment_method"]
            funding_name = (
                card_name_map.get(fx["credit_card_id"], "—")
                if payment_method == "credit_card"
                else account_name_map.get(fx["bank_account_id"], "—")
            )
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([3, 2, 2, 2, 2, 2, 1, 1])
            c1.write(fx["name"])
            c2.write(f"${fx['amount']:,.2f}")
            c3.write(f"Day {fx['due_day']}")
            c4.write("Credit card" if payment_method == "credit_card" else "Debit")
            c5.write(funding_name)
            c6.write(fx["subcategory"] or "")
            if fx["active"]:
                if c7.button("Edit", key=f"edit_{fx['id']}"):
                    st.session_state.editing_fx = dict(fx)
                if c8.button(
                    "Delete",
                    key=f"delete_{fx['id']}",
                    disabled=not can_delete_for_selected_month,
                ):
                    deactivate_fixed_expense(fx["id"])
                    st.session_state.editing_fx = None
                    st.success("Fixed expense deleted.")
                    st.rerun()

        st.divider()
        st.markdown("#### Add / Edit Fixed Expense")

        fx = st.session_state.editing_fx or {}

        with st.form("fixed_expense_form"):
            payment_method_options = ["Debit", "Credit card"]
            default_payment_method = (
                "Credit card" if fx.get("payment_method") == "credit_card" else "Debit"
            )
            name = st.text_input("Name", value=fx.get("name", ""))
            amount = st.number_input(
                "Amount", min_value=0.0, step=1.0, value=fx.get("amount", 0.0)
            )
            due_day = st.number_input(
                "Due day (1–31)", min_value=1, max_value=31, value=fx.get("due_day", 1)
            )
            payment_method_label = st.selectbox(
                "Payment method",
                options=payment_method_options,
                index=payment_method_options.index(default_payment_method),
            )
            default_account = None
            if fx.get("bank_account_id"):
                for label, acct_id in account_label_map.items():
                    if acct_id == fx["bank_account_id"]:
                        default_account = label
                        break
            default_card = None
            if fx.get("credit_card_id"):
                for label, card_id in card_label_map.items():
                    if card_id == fx["credit_card_id"]:
                        default_card = label
                        break
            bank_account_label = st.selectbox(
                "Bank account (optional)",
                options=account_options,
                index=account_options.index(default_account)
                if default_account in account_options
                else 0,
            )
            credit_card_label = st.selectbox(
                "Credit card",
                options=card_options,
                index=card_options.index(default_card)
                if default_card in card_options
                else 0,
            )
            subcategory = st.text_input(
                "Subcategory", value=fx.get("subcategory", "") or ""
            )
            submitted = st.form_submit_button("Save")

        if submitted:
            if not name or amount <= 0:
                st.error("Name and amount are required.")
            elif payment_method_label == "Credit card" and credit_card_label == "—":
                st.error("Select a credit card for credit-card fixed expenses.")
            else:
                payment_method = payment_method_label.lower().replace(" ", "_")
                bank_account_id = (
                    account_label_map.get(bank_account_label)
                    if payment_method == "debit"
                    else None
                )
                credit_card_id = (
                    card_label_map.get(credit_card_label)
                    if payment_method == "credit_card"
                    else None
                )
                upsert_fixed_expense(
                    name,
                    amount,
                    due_day,
                    subcategory or None,
                    payment_method,
                    bank_account_id,
                    credit_card_id,
                )
                st.session_state.editing_fx = None
                st.success("Fixed expense saved.")
                st.rerun()

    # ---------------- Income ----------------
    with income_tab:
        st.markdown("### Income")
        st.info(
            "Income sources apply to future months only. "
            "They are copied as transactions when a month is initialized."
        )

        accounts = get_bank_accounts()
        account_name_map = {a["id"]: a["name"] for a in accounts}
        account_label_map = {
            f"{a['name']} (id {a['id']})": a["id"] for a in accounts
        }
        account_options = ["—"] + list(account_label_map.keys())

        incomes = get_income_sources()

        for inc in incomes:
            c1, c2, c3, c4, c5, c6, c7 = st.columns([3, 2, 2, 2, 2, 1, 1])
            c1.write(inc["name"])
            c2.write(f"${inc['amount']:,.2f}")
            c3.write(f"Day {inc['due_day']}")
            c4.write(account_name_map.get(inc["bank_account_id"], "—"))
            c5.write(inc["subcategory"] or "")
            if inc["active"]:
                if c6.button("Edit", key=f"edit_income_{inc['id']}"):
                    st.session_state.editing_income = dict(inc)
                if c7.button(
                    "Delete",
                    key=f"delete_income_{inc['id']}",
                    disabled=not can_delete_for_selected_month,
                ):
                    deactivate_income_source(inc["id"])
                    st.session_state.editing_income = None
                    st.success("Income source deleted.")
                    st.rerun()

        st.divider()
        st.markdown("#### Add / Edit Income Source")

        inc = st.session_state.editing_income or {}

        with st.form("income_form"):
            name = st.text_input("Name", value=inc.get("name", ""))
            amount = st.number_input(
                "Amount", min_value=0.0, step=1.0, value=inc.get("amount", 0.0)
            )
            due_day = st.number_input(
                "Due day (1–31)", min_value=1, max_value=31, value=inc.get("due_day", 1)
            )
            default_account = None
            if inc.get("bank_account_id"):
                for label, acct_id in account_label_map.items():
                    if acct_id == inc["bank_account_id"]:
                        default_account = label
                        break
            bank_account_label = st.selectbox(
                "Bank account (optional)",
                options=account_options,
                index=account_options.index(default_account)
                if default_account in account_options
                else 0,
            )
            subcategory = st.text_input(
                "Subcategory", value=inc.get("subcategory", "") or ""
            )
            submitted = st.form_submit_button("Save")

        if submitted:
            if not name or amount <= 0:
                st.error("Name and amount are required.")
            else:
                bank_account_id = account_label_map.get(bank_account_label)
                upsert_income_source(
                    name, amount, due_day, subcategory or None, bank_account_id
                )
                st.session_state.editing_income = None
                st.success("Income source saved.")
                st.rerun()

    # ---------------- Objectives ----------------
    with objectives_tab:
        if st.session_state.objectives_saved:
            st.success("The new objectives have been successfully saved.")
            st.session_state.objectives_saved = False

        st.markdown("### Budget Objectives (% of income)")

        current = get_active_objectives()

        with st.form("objectives_form"):
            fixed_pct = st.number_input(
                "Fixed expenses (%)",
                min_value=0.0,
                max_value=1.0,
                value=current.get("Fixed", 0.4),
                step=0.01,
            )
            variable_pct = st.number_input(
                "Variable expenses (%)",
                min_value=0.0,
                max_value=1.0,
                value=current.get("Variable", 0.3),
                step=0.01,
            )
            savings_pct = st.number_input(
                "Savings (%)",
                min_value=0.0,
                max_value=1.0,
                value=current.get("Savings", 0.2),
                step=0.01,
            )
            submitted = st.form_submit_button("Save objectives")

        if submitted:
            if fixed_pct + variable_pct + savings_pct > 1.0:
                st.error("Total allocation cannot exceed 100%.")
            else:

                upsert_objective("Fixed", fixed_pct)
                upsert_objective("Variable", variable_pct)
                upsert_objective("Savings", savings_pct)

                st.session_state.objectives_saved = True
                st.rerun()

# ======================================================
# Restore Backup TAB
# ======================================================
with backup_data_tab:
    if st.session_state.get("backup_restored"):
        st.success("Backup restored successfully.")
        st.session_state.pop("backup_restored", None)

    st.divider()
    st.markdown("### Restore from backup")

    st.warning(
        "Uploading a backup will replace your current data. "
        "This action cannot be undone."
    )

    uploaded_db = st.file_uploader(
        "Upload your SBP backup data (.db file)",
        type=["db"],
        key="restore_uploader",
    )

    # ---- Read file ONCE ----
    if uploaded_db is not None and "uploaded_db_bytes" not in st.session_state:
        st.session_state.uploaded_db_bytes = uploaded_db.read()

    db_bytes = st.session_state.get("uploaded_db_bytes")

    if db_bytes:

        if not is_valid_sqlite_db(db_bytes):
            st.error("This file does not appear to be a valid SQLite database.")
            st.session_state.pop("uploaded_db_bytes", None)
        else:
            confirm = st.checkbox(
                "I understand this will overwrite my current data"
            )

            restore_clicked = st.button(
                "Restore backup",
                disabled=not confirm,
                type="primary",
            )

            if restore_clicked:
                user_db_path = Path("data") / f"{st.session_state.user}.db"
                user_db_path.parent.mkdir(parents=True, exist_ok=True)

                with open(user_db_path, "wb") as f:
                    f.write(db_bytes)

                st.session_state.pop("uploaded_db_bytes", None)
                st.session_state.pop("restore_uploader", None)
                st.session_state.backup_restored = True

                st.rerun()
