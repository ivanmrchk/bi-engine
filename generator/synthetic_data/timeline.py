"""Calendar helpers: which months we simulate, and moments inside them."""

import calendar
import random
from datetime import date, datetime
from zoneinfo import ZoneInfo

from synthetic_data.calibration import FIRST_MONTH, LAST_MONTH

BUSINESS_TIMEZONE = ZoneInfo("America/Los_Angeles")


def simulated_months() -> list[date]:
    """The first day of every month from FIRST_MONTH through LAST_MONTH."""
    months = []
    month = FIRST_MONTH
    while month <= LAST_MONTH:
        months.append(month)
        month = _first_day_of_next_month(month)
    return months


def progress_through_history(month: date) -> float:
    """0.0 for the first simulated month, 1.0 for the last one."""
    return progress_since(FIRST_MONTH, month)


def progress_since(start_month: date, month: date) -> float:
    """0.0 at start_month, rising steadily to 1.0 at the last simulated month."""
    months_elapsed = _months_between(start_month, month)
    total_months = _months_between(start_month, LAST_MONTH)
    return months_elapsed / total_months


def blend(start_value: float, end_value: float, progress: float) -> float:
    """The value `progress` of the way from start_value to end_value."""
    return start_value + (end_value - start_value) * progress


def random_moment_in_month(month: date, randomness: random.Random) -> datetime:
    """A random time during business hours (7am-7pm) on some day of the month."""
    days_in_month = calendar.monthrange(month.year, month.month)[1]
    return datetime(
        month.year,
        month.month,
        randomness.randint(1, days_in_month),
        randomness.randint(7, 18),
        randomness.randint(0, 59),
        tzinfo=BUSINESS_TIMEZONE,
    )


def _months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def _first_day_of_next_month(month: date) -> date:
    if month.month == 12:
        return date(month.year + 1, 1, 1)
    return date(month.year, month.month + 1, 1)
