"""Why a city's revenue changed: fewer jobs, fewer that became real work, or smaller jobs.

Revenue from the jobs booked in a period breaks down exactly as

    revenue = booked jobs  x  conversion              x  average ticket
              (demand)        (real jobs / booked)       (revenue / real jobs)

so comparing each factor with the same months a year earlier shows which
one moved. At a few dozen jobs per city, much of that movement is chance,
so each factor's change is tested against it (see change_statistics) and
only clear declines are named as reasons. Periods span several months for
the same reason: more jobs, less noise.
"""

from datetime import date

from pydantic import computed_field
from pydantic.dataclasses import dataclass
from sqlalchemy import Connection, text

from app.analysis.change_statistics import (
    CLEAR_CHANGE_Z_SCORE,
    count_change_z_score,
    mean_change_z_score,
    share_change_z_score,
)
from app.analysis.months import add_months

ALL_CITIES = "All cities"
RECENT = "recent"
YEAR_BEFORE = "year_before"


@dataclass(frozen=True)
class Period:
    first_month: date
    last_month: date


@dataclass(frozen=True)
class CityPeriod:
    """The jobs booked in one city during one period."""

    booked_jobs: int = 0
    real_jobs: int = 0
    revenue_cents: int = 0
    # Ticket prices are skewed (a few big jobs), so changes in them are
    # tested on a log scale, where they behave like an ordinary bell curve.
    mean_log_ticket: float | None = None
    variance_log_ticket: float | None = None
    search_impressions: int | None = None  # None when Search Console history doesn't reach back

    @computed_field
    @property
    def conversion(self) -> float | None:
        return self.real_jobs / self.booked_jobs if self.booked_jobs else None

    @computed_field
    @property
    def average_ticket_cents(self) -> int | None:
        return round(self.revenue_cents / self.real_jobs) if self.real_jobs else None


@dataclass(frozen=True)
class FactorChange:
    factor: str
    change: float | None  # -0.4 means 40% lower than a year before
    z_score: float | None

    @computed_field
    @property
    def is_clear(self) -> bool:
        return self.z_score is not None and abs(self.z_score) >= CLEAR_CHANGE_Z_SCORE


@dataclass(frozen=True)
class CityDiagnosis:
    city: str
    location: str | None
    recent: CityPeriod
    year_before: CityPeriod

    @computed_field
    @property
    def revenue_change(self) -> float | None:
        return _relative_change(self.year_before.revenue_cents, self.recent.revenue_cents)

    @computed_field
    @property
    def search_impressions_change(self) -> float | None:
        if self.year_before.search_impressions is None or self.recent.search_impressions is None:
            return None
        return _relative_change(self.year_before.search_impressions, self.recent.search_impressions)

    @computed_field
    @property
    def factors(self) -> list[FactorChange]:
        before, recent = self.year_before, self.recent
        ticket_z_score = None
        if before.mean_log_ticket is not None and recent.mean_log_ticket is not None:
            ticket_z_score = mean_change_z_score(
                before.mean_log_ticket, before.variance_log_ticket or 0.0, before.real_jobs,
                recent.mean_log_ticket, recent.variance_log_ticket or 0.0, recent.real_jobs,
            )
        return [
            FactorChange(
                "demand",
                _relative_change(before.booked_jobs, recent.booked_jobs),
                count_change_z_score(before.booked_jobs, recent.booked_jobs),
            ),
            FactorChange(
                "conversion",
                _relative_change(before.conversion, recent.conversion),
                share_change_z_score(before.real_jobs, before.booked_jobs, recent.real_jobs, recent.booked_jobs),
            ),
            FactorChange(
                "ticket size",
                _relative_change(before.average_ticket_cents, recent.average_ticket_cents),
                ticket_z_score,
            ),
        ]

    @computed_field
    @property
    def reasons(self) -> list[str]:
        """The factors that clearly fell, the clearest first."""
        clear_declines = [factor for factor in self.factors if factor.is_clear and factor.z_score < 0]
        return [factor.factor for factor in sorted(clear_declines, key=lambda factor: factor.z_score)]


@dataclass(frozen=True)
class LaggingCitiesReport:
    recent_period: Period
    year_before_period: Period
    company: CityDiagnosis
    cities: list[CityDiagnosis]  # the biggest revenue decline first; new cities last


def diagnose_cities(
    connection: Connection, last_month: date, months: int = 6, location: str | None = None
) -> LaggingCitiesReport:
    recent = Period(add_months(last_month, -(months - 1)), last_month)
    year_before = Period(add_months(recent.first_month, -12), add_months(last_month, -12))

    periods = _job_numbers(connection, recent, year_before, location)
    for (city, period_name), impressions in _search_impressions(connection, recent, year_before, location).items():
        numbers = periods.setdefault((city, period_name), {})
        numbers["search_impressions"] = impressions

    location_by_city = {}
    for (city, _), numbers in periods.items():
        city_location = numbers.pop("location", None)
        if city_location is not None:
            location_by_city[city] = city_location

    diagnoses = {
        city: CityDiagnosis(
            city=city,
            location=location_by_city.get(city) or location,
            recent=CityPeriod(**periods.get((city, RECENT), {})),
            year_before=CityPeriod(**periods.get((city, YEAR_BEFORE), {})),
        )
        for city in {city for city, _ in periods}
    }
    company = diagnoses.pop(ALL_CITIES, CityDiagnosis(ALL_CITIES, location, CityPeriod(), CityPeriod()))
    cities = sorted(diagnoses.values(), key=_biggest_decline_first)
    return LaggingCitiesReport(recent, year_before, company, cities)


def _job_numbers(connection: Connection, recent: Period, year_before: Period, location: str | None) -> dict:
    """{(city, period): numbers}. GROUPING SETS adds each period's all-cities total in the same pass."""
    rows = connection.execute(text("""
        WITH jobs_in_periods AS (
            SELECT
                *,
                CASE WHEN booked_month >= :recent_first THEN 'recent' ELSE 'year_before' END AS period
            FROM analytics.booked_jobs
            WHERE (booked_month BETWEEN :recent_first AND :recent_last
                   OR booked_month BETWEEN :before_first AND :before_last)
              AND (CAST(:location AS TEXT) IS NULL OR location_name = :location)
        )
        SELECT
            coalesce(city, :all_cities) AS city,
            -- GROUPING(city) is 1 on the all-cities total rows, which span locations
            CASE WHEN GROUPING(city) = 1 THEN NULL ELSE max(location_name) END AS location,
            period,
            count(*) AS booked_jobs,
            count(*) FILTER (WHERE is_real_job) AS real_jobs,
            coalesce(sum(total_cents) FILTER (WHERE is_real_job), 0) AS revenue_cents,
            avg(ln(total_cents)) FILTER (WHERE is_real_job) AS mean_log_ticket,
            var_samp(ln(total_cents)) FILTER (WHERE is_real_job) AS variance_log_ticket
        FROM jobs_in_periods
        GROUP BY GROUPING SETS ((city, period), (period))
    """), _period_parameters(recent, year_before, location)).mappings()
    return {
        (row["city"], row["period"]): {key: value for key, value in row.items() if key not in ("city", "period")}
        for row in rows
    }


def _search_impressions(connection: Connection, recent: Period, year_before: Period, location: str | None) -> dict:
    """{(city, period): impressions}, or nothing at all when the history doesn't reach the year-before period."""
    first_search_day = connection.execute(text("SELECT min(day) FROM clean.search_daily_totals")).scalar_one()
    if first_search_day is None or first_search_day > year_before.first_month:
        return {}
    rows = connection.execute(text("""
        WITH searches_in_periods AS (
            SELECT
                search.city,
                search.impressions,
                CASE WHEN search.month >= :recent_first THEN 'recent' ELSE 'year_before' END AS period
            FROM analytics.city_search_months AS search
            JOIN (SELECT DISTINCT city, location_name FROM reference.service_area_zip_codes) AS area USING (city)
            WHERE (search.month BETWEEN :recent_first AND :recent_last
                   OR search.month BETWEEN :before_first AND :before_last)
              AND (CAST(:location AS TEXT) IS NULL OR area.location_name = :location)
        )
        SELECT coalesce(city, :all_cities), period, sum(impressions)
        FROM searches_in_periods
        GROUP BY GROUPING SETS ((city, period), (period))
    """), _period_parameters(recent, year_before, location))
    return {(city, period): int(impressions) for city, period, impressions in rows}


def _period_parameters(recent: Period, year_before: Period, location: str | None) -> dict:
    return {
        "recent_first": recent.first_month, "recent_last": recent.last_month,
        "before_first": year_before.first_month, "before_last": year_before.last_month,
        "location": location, "all_cities": ALL_CITIES,
    }


def _biggest_decline_first(diagnosis: CityDiagnosis) -> tuple[bool, float]:
    """Cities with no year-before revenue to compare (new ones) sort last."""
    has_no_comparison = diagnosis.revenue_change is None
    return has_no_comparison, diagnosis.revenue_change or 0.0


def _relative_change(before: float | None, after: float | None) -> float | None:
    if not before or after is None:
        return None
    return (after - before) / before
