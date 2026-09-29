from datetime import date

import pytest

from app.analysis.change_statistics import (
    count_change_z_score,
    mean_change_z_score,
    share_change_z_score,
)
from app.analysis.city_diagnosis import CityDiagnosis, CityPeriod
from app.analysis.months import add_months


def city(recent: CityPeriod, year_before: CityPeriod) -> CityDiagnosis:
    return CityDiagnosis("Bellevue", "Eastside", recent=recent, year_before=year_before)


def period(booked, real, revenue_cents, mean_log_ticket=10.0, variance_log_ticket=0.5) -> CityPeriod:
    return CityPeriod(booked, real, revenue_cents, mean_log_ticket, variance_log_ticket)


# --- change statistics -------------------------------------------------------


def test_the_same_relative_change_is_clearer_with_more_jobs():
    assert abs(count_change_z_score(10, 5)) < 2  # 10 -> 5 jobs could be chance
    assert abs(count_change_z_score(100, 50)) > 2  # 100 -> 50 jobs almost certainly isn't


def test_an_unchanged_share_is_not_a_change():
    assert share_change_z_score(30, 50, 60, 100) == 0.0


def test_a_share_that_halves_across_many_jobs_is_clear():
    assert share_change_z_score(60, 100, 30, 100) < -2


def test_a_mean_that_moves_by_much_more_than_its_spread_is_clear():
    assert mean_change_z_score(10.0, 0.1, 40, 9.0, 0.1, 40) < -2


def test_no_verdict_without_data():
    assert count_change_z_score(0, 5) is None
    assert share_change_z_score(0, 0, 3, 5) is None
    assert mean_change_z_score(10.0, 0.1, 1, 9.0, 0.1, 40) is None


# --- the revenue breakdown ------------------------------------------------------


def test_revenue_breaks_down_into_demand_conversion_and_ticket():
    diagnosis = city(
        recent=period(booked=40, real=20, revenue_cents=40_000),      # conversion 50%, ticket 2,000
        year_before=period(booked=40, real=32, revenue_cents=64_000),  # conversion 80%, ticket 2,000
    )
    changes = {factor.factor: factor.change for factor in diagnosis.factors}

    # approx: (0.5 - 0.8) / 0.8 isn't exactly -0.375 in floating point
    assert changes == pytest.approx({"demand": 0.0, "conversion": -0.375, "ticket size": 0.0})
    assert diagnosis.revenue_change == pytest.approx(-0.375)


def test_only_clear_declines_are_named_as_reasons():
    diagnosis = city(
        recent=period(booked=100, real=40, revenue_cents=80_000),
        year_before=period(booked=100, real=80, revenue_cents=160_000),
    )

    assert diagnosis.reasons == ["conversion"]


def test_a_small_city_gets_no_reasons_from_noise():
    diagnosis = city(
        recent=period(booked=4, real=2, revenue_cents=4_000),
        year_before=period(booked=5, real=4, revenue_cents=8_000),
    )

    assert diagnosis.revenue_change == -0.5
    assert diagnosis.reasons == []


def test_a_new_city_has_nothing_to_compare_against():
    diagnosis = city(recent=period(booked=12, real=8, revenue_cents=20_000), year_before=CityPeriod())

    assert diagnosis.revenue_change is None
    assert all(factor.change is None for factor in diagnosis.factors)


def test_months_count_across_year_boundaries():
    assert add_months(date(2026, 3, 1), -5) == date(2025, 10, 1)
    assert add_months(date(2025, 12, 1), 1) == date(2026, 1, 1)
