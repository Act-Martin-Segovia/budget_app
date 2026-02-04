import sys
import json
from pathlib import Path
from datetime import date
from collections.abc import Mapping

import streamlit as st
import bcrypt

ROOT = Path(__file__).resolve()
while not (ROOT / ".git").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from budget_app.db.db import (
    add_transaction,
    close_month,
    init_db,
    open_month,
    month_exists,
)

from budget_app.app.helper_functions import (
    current_month_id,
    list_known_months,
    get_month_snapshot,
    get_month_status,
    get_previous_month_ending_balance,
    get_month_totals_by_category,
    get_total_income,
    get_active_objectives,
    get_category_actual,
    get_category_planned,
    generate_month_options,
    get_fixed_expenses,
    upsert_fixed_expense,
    deactivate_fixed_expense,
    get_income_sources,
    upsert_income_source,
    deactivate_income_source,
    upsert_objective,
    has_fixed_expenses,
    has_income_sources,
    has_objectives,
    preview_fixed_expenses_for_month,
    preview_income_for_month,
    get_transactions_for_month,
    get_variable_by_payment_method,
    get_half_month_splits,
    get_oldest_open_month,
    is_valid_sqlite_db,
)

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

if "pending_tx" not in st.session_state:
    st.session_state.pending_tx = None

if "objectives_saved" not in st.session_state:
    st.session_state.objectives_saved = False

if "editing_fx" not in st.session_state:
    st.session_state.editing_fx = None

if "editing_income" not in st.session_state:
    st.session_state.editing_income = None

if "confirm_close_month_for" not in st.session_state:
    st.session_state.confirm_close_month_for = None

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
        if preview:
            st.divider()
            st.markdown("**Fixed expenses that will apply:**")

            for fx in preview:
                c1, c2, c3 = st.columns([2, 4, 2])
                c1.write(fx["date"].strftime("%Y-%m-%d"))
                c2.write(f"{fx['name']} ({fx['subcategory'] or '—'})")
                c3.write(f"${fx['amount']:,.2f}")
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

        if missing_setup:
            st.warning(
                "Before initializing a month, please set up: "
                + ", ".join(missing_setup)
                + ".\n\nGo to the **Settings** tab to complete the setup."
            )
        else:
            prev_balance = get_previous_month_ending_balance(selected_month)

            carry_over = True  # default

            if prev_balance is not None and prev_balance != 0:
                st.markdown(
                    f"**Unused balance from previous month:** "
                    f"${prev_balance:,.2f}"
                )

                carry_over = st.radio(
                    "How should this balance be treated?",
                    options=[
                        "Carry it over as starting balance",
                        "Ignore it (start from 0)",
                    ],
                    index=0,
                ) == "Carry it over as starting balance"

            if st.button("Initialize month"):
                starting_balance = prev_balance if carry_over and prev_balance else 0.0

                open_month(
                    selected_month,
                    starting_balance=starting_balance,
                )

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
                '<div class="subsection-header">Mid Month Cashflow</div>',
                unsafe_allow_html=True,
            )
            splits = get_half_month_splits(selected_month)
            header_cols = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2])
            header_labels = [
                "Period",
                "Income",
                "Fixed expenses",
                "Variable expenses",
                "Savings",
                "Balance",
            ]
            for col, label in zip(header_cols, header_labels):
                col.markdown(f'<div class="alloc-label">{label}</div>', unsafe_allow_html=True)

            periods = [("Day 1–15", "first"), ("Day 16–eom", "second")]
            for label, key in periods:
                income = splits.get("Income", {}).get(key, 0.0)
                fixed = splits.get("Fixed", {}).get(key, 0.0)
                variable = splits.get("Variable", {}).get(key, 0.0)
                savings = splits.get("Savings", {}).get(key, 0.0)
                balance = income - fixed - variable - savings
                balance_class = "good" if balance >= 0 else "bad"
                if balance < 0:
                    balance_icon = "🚨"
                elif balance < 100:
                    balance_icon = "⚠️"
                else:
                    balance_icon = "✅"

                c1, c2, c3, c4, c5, c6 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2])
                c1.markdown(f'<div class="alloc-title">{label}</div>', unsafe_allow_html=True)
                c2.markdown(
                    f'<div class="alloc-value inflow">${income:,.2f}</div>',
                    unsafe_allow_html=True,
                )
                c3.markdown(
                    f'<div class="alloc-value outflow">${fixed:,.2f}</div>',
                    unsafe_allow_html=True,
                )
                c4.markdown(
                    f'<div class="alloc-value outflow">${variable:,.2f}</div>',
                    unsafe_allow_html=True,
                )
                c5.markdown(
                    f'<div class="alloc-value outflow">${savings:,.2f}</div>',
                    unsafe_allow_html=True,
                )
                c6.markdown(
                    f'<div class="alloc-value {balance_class}">'
                    f'${balance:,.2f} {balance_icon}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

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

            CATEGORY_LABELS = {
                "Income": "Income",
                "Variable": "Variable Expense",
                "Savings": "Savings",
            }

            with st.form("transaction_form", clear_on_submit=True):
                tx_date = st.date_input("Date")
                category_label = st.selectbox("Category", list(CATEGORY_LABELS.values()))
                subcategory = st.text_input("Subcategory")
                amount = st.number_input("Amount", min_value=0.0, step=1.0)
                payment_method = st.selectbox("Payment method", ["Debit", "Credit card"])
                note = st.text_input("Note (optional)")
                submitted = st.form_submit_button("Add transaction")

            if submitted:
                category = next(
                    k for k, v in CATEGORY_LABELS.items() if v == category_label
                )
                subcategory = subcategory.strip()
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
                    subcategory = subcategory or None
                    signed_amount = amount if category == "Income" else -amount

                    if category == "Income":
                        add_transaction(
                            date=tx_date.isoformat(),
                            month_id=selected_month,
                            amount=signed_amount,
                            category=category,
                            subcategory=subcategory,
                            payment_method=None,
                            note=note,
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
                                "amount": signed_amount,
                                "category": category,
                                "subcategory": subcategory,
                                "payment_method": payment_method,
                                "note": note,
                                "planned": planned,
                                "simulated": simulated,
                            }
                        else:
                            add_transaction(
                                date=tx_date.isoformat(),
                                month_id=selected_month,
                                amount=signed_amount,
                                category=category,
                                subcategory=subcategory,
                                payment_method=payment_method.lower().replace(" ", "_"),
                                note=note,
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
                    add_transaction(
                        date=pending["date"],
                        month_id=pending["month_id"],
                        amount=pending["amount"],
                        category=pending["category"],
                        subcategory=pending["subcategory"],
                        payment_method=pending["payment_method"].lower().replace(" ", "_"),
                        note=pending["note"],
                    )
                    st.session_state.pending_tx = None
                    st.success("Transaction added.")
                    st.rerun()
            st.divider()

        transactions = get_transactions_for_month(selected_month)

        st.subheader(f"Transaction Details — {selected_month}")
        if not transactions:
            st.info("No transactions recorded for this month yet.")
        else:
            filter_col, group_col = st.columns(2)
            with filter_col:
                filter_labels = st.multiselect(
                    "Filter by category",
                    options=["Fixed", "Variable", "Savings", "Income"],
                    default=["Fixed", "Variable", "Savings", "Income"],
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
        "1. Define your fixed expenses\n"
        "2. Add your income sources\n"
        "3. Set your budget objectives\n"
        "4. Then initialize your first month from the Dashboard"
    )
    if not can_delete_for_selected_month:
        st.warning(
            f"Month {selected_month} is already initialized. "
            "Fixed expenses and income sources can only be deleted "
            "before initializing the selected month."
        )

    fixed_tab, income_tab, objectives_tab = st.tabs(
        ["Fixed Expenses", "Income", "Budget Objectives"]
    )

    # ---------------- Fixed expenses ----------------
    with fixed_tab:
        st.markdown("### Fixed Expenses")
        st.info(
            "Fixed expenses apply to future months only. "
            "They are copied as transactions when a month is initialized."
        )

        expenses = get_fixed_expenses()

        for fx in expenses:
            c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 1, 1])
            c1.write(fx["name"])
            c2.write(f"${fx['amount']:,.2f}")
            c3.write(f"Day {fx['due_day']}")
            c4.write(fx["subcategory"] or "")
            if fx["active"]:
                if c5.button("Edit", key=f"edit_{fx['id']}"):
                    st.session_state.editing_fx = dict(fx)
                if c6.button(
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
            name = st.text_input("Name", value=fx.get("name", ""))
            amount = st.number_input(
                "Amount", min_value=0.0, step=1.0, value=fx.get("amount", 0.0)
            )
            due_day = st.number_input(
                "Due day (1–31)", min_value=1, max_value=31, value=fx.get("due_day", 1)
            )
            subcategory = st.text_input(
                "Subcategory", value=fx.get("subcategory", "") or ""
            )
            submitted = st.form_submit_button("Save")

        if submitted:
            if not name or amount <= 0:
                st.error("Name and amount are required.")
            else:
                upsert_fixed_expense(name, amount, due_day, subcategory or None)
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

        incomes = get_income_sources()

        for inc in incomes:
            c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 1, 1])
            c1.write(inc["name"])
            c2.write(f"${inc['amount']:,.2f}")
            c3.write(f"Day {inc['due_day']}")
            c4.write(inc["subcategory"] or "")
            if inc["active"]:
                if c5.button("Edit", key=f"edit_income_{inc['id']}"):
                    st.session_state.editing_income = dict(inc)
                if c6.button(
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
            subcategory = st.text_input(
                "Subcategory", value=inc.get("subcategory", "") or ""
            )
            submitted = st.form_submit_button("Save")

        if submitted:
            if not name or amount <= 0:
                st.error("Name and amount are required.")
            else:
                upsert_income_source(name, amount, due_day, subcategory or None)
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
