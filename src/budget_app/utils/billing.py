from datetime import date

from dateutil.relativedelta import relativedelta


def month_id_from_date(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def clamp_day(year: int, month: int, day: int) -> int:
    last_day = (date(year, month, 1) + relativedelta(months=1, days=-1)).day
    return min(day, last_day)


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
