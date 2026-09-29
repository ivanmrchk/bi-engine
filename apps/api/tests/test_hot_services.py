import pytest

from app.analysis.hot_services import Period, ServiceMonth
from app.analysis.months import NotAMonth, parse_month


def service_month(this=Period(10, 50_000), previous=Period(8, 40_000), last_year=Period(5, 25_000)) -> ServiceMonth:
    return ServiceMonth("Panel Upgrade", this_month=this, previous_month=previous, same_month_last_year=last_year)


def test_revenue_change_is_relative_to_the_earlier_month():
    month = service_month(this=Period(10, 50_000), last_year=Period(5, 25_000))

    assert month.revenue_change_vs_last_year == 1.0  # doubled


def test_no_change_can_be_computed_from_nothing():
    month = service_month(previous=Period(0, 0))

    assert month.revenue_change_vs_previous_month is None


def test_average_ticket_is_revenue_per_job():
    assert service_month(this=Period(4, 10_000)).average_ticket_cents == 2_500


def test_a_month_without_jobs_has_no_average_ticket():
    assert service_month(this=Period(0, 0)).average_ticket_cents is None


def test_a_change_between_small_months_is_not_meaningful():
    month = service_month(this=Period(5, 9_000), last_year=Period(1, 1_000))

    assert month.revenue_change_vs_last_year == 8.0  # "+800%"
    assert not month.has_enough_jobs_vs_last_year


def test_a_change_between_busy_months_is_meaningful():
    assert service_month(this=Period(12, 1), last_year=Period(6, 1)).has_enough_jobs_vs_last_year


def test_months_are_read_as_year_and_month():
    assert parse_month("2026-06").isoformat() == "2026-06-01"


@pytest.mark.parametrize("text", ["June", "2026-6", "2026-13", "2026-06-01", ""])
def test_anything_else_is_not_a_month(text):
    with pytest.raises(NotAMonth):
        parse_month(text)
