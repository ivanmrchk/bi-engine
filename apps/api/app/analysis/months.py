"""Months as the analysis talks about them: '2026-06' means June 2026."""

import re
from datetime import date

MONTH_FORMAT = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


class NotAMonth(ValueError):
    pass


def parse_month(text: str) -> date:
    """'2026-06' -> date(2026, 6, 1)."""
    match = MONTH_FORMAT.match(text)
    if match is None:
        raise NotAMonth(f"{text!r} is not a month in YYYY-MM form")
    return date(int(match.group(1)), int(match.group(2)), 1)


def add_months(month: date, count: int) -> date:
    """The first day of the month `count` months later (or earlier, if negative)."""
    months_since_year_zero = month.year * 12 + (month.month - 1) + count
    return date(months_since_year_zero // 12, months_since_year_zero % 12 + 1, 1)
