from datetime import date

from budget_app.utils.billing import compute_credit_card_cycle


def test_compute_credit_card_cycle_uses_current_statement_when_before_close():
    statement_month_id, due_month_id, due_date = compute_credit_card_cycle(
        date(2026, 4, 10),
        statement_close_day=20,
        due_day=15,
    )

    assert statement_month_id == "2026-04"
    assert due_month_id == "2026-05"
    assert due_date == date(2026, 5, 15)


def test_compute_credit_card_cycle_rolls_after_statement_close():
    statement_month_id, due_month_id, due_date = compute_credit_card_cycle(
        date(2026, 4, 21),
        statement_close_day=20,
        due_day=15,
    )

    assert statement_month_id == "2026-05"
    assert due_month_id == "2026-06"
    assert due_date == date(2026, 6, 15)


def test_compute_credit_card_cycle_clamps_due_day_for_short_months():
    statement_month_id, due_month_id, due_date = compute_credit_card_cycle(
        date(2026, 1, 31),
        statement_close_day=31,
        due_day=31,
    )

    assert statement_month_id == "2026-01"
    assert due_month_id == "2026-02"
    assert due_date == date(2026, 2, 28)
