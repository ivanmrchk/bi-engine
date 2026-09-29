"""Which services are hot: this month against last month and the same month last year.

Last month shows momentum; the same month last year strips out seasonality
(generators always pick up in the fall), so growth against it is the
fairer sign that a service is genuinely heating up.
"""

from datetime import date

from pydantic import computed_field
from pydantic.dataclasses import dataclass
from sqlalchemy import Connection, text

# Going from 1 job to 5 is "+400%" but says little. A change counts as
# meaningful only when both months have at least this many jobs.
MINIMUM_JOBS_FOR_A_MEANINGFUL_CHANGE = 5


@dataclass(frozen=True)
class Period:
    """Real jobs finished in one month, and what they were billed."""

    jobs: int
    revenue_cents: int


@dataclass(frozen=True)
class ServiceMonth:
    service: str
    this_month: Period
    previous_month: Period
    same_month_last_year: Period

    # computed_field makes these derived values part of the API response too.
    @computed_field
    @property
    def average_ticket_cents(self) -> int | None:
        if self.this_month.jobs == 0:
            return None
        return round(self.this_month.revenue_cents / self.this_month.jobs)

    @computed_field
    @property
    def revenue_change_vs_previous_month(self) -> float | None:
        return _relative_change(self.previous_month.revenue_cents, self.this_month.revenue_cents)

    @computed_field
    @property
    def revenue_change_vs_last_year(self) -> float | None:
        return _relative_change(self.same_month_last_year.revenue_cents, self.this_month.revenue_cents)

    @computed_field
    @property
    def has_enough_jobs_vs_previous_month(self) -> bool:
        return min(self.this_month.jobs, self.previous_month.jobs) >= MINIMUM_JOBS_FOR_A_MEANINGFUL_CHANGE

    @computed_field
    @property
    def has_enough_jobs_vs_last_year(self) -> bool:
        return min(self.this_month.jobs, self.same_month_last_year.jobs) >= MINIMUM_JOBS_FOR_A_MEANINGFUL_CHANGE


def hot_services(
    connection: Connection, month: date, location: str | None = None, city: str | None = None
) -> list[ServiceMonth]:
    """Every service with work in any of the three months, highest revenue first.

    `location` and `city` narrow the numbers; leaving them out means the whole company.
    """
    rows = connection.execute(text("""
        WITH filtered AS (
            SELECT month, service, sum(jobs) AS jobs, sum(revenue_cents) AS revenue_cents
            FROM analytics.service_months
            WHERE (CAST(:location AS TEXT) IS NULL OR location_name = :location)
              AND (CAST(:city AS TEXT) IS NULL OR city = :city)
            GROUP BY month, service
        ),
        compared_months AS (
            SELECT
                CAST(:month AS DATE) AS this_month,
                CAST(:month AS DATE) - INTERVAL '1 month' AS previous_month,
                CAST(:month AS DATE) - INTERVAL '1 year' AS same_month_last_year
        ),
        services AS (
            SELECT DISTINCT filtered.service
            FROM filtered, compared_months
            WHERE filtered.month IN (this_month, previous_month, same_month_last_year)
        )
        SELECT
            services.service,
            coalesce(this_period.jobs, 0), coalesce(this_period.revenue_cents, 0),
            coalesce(previous_period.jobs, 0), coalesce(previous_period.revenue_cents, 0),
            coalesce(last_year_period.jobs, 0), coalesce(last_year_period.revenue_cents, 0)
        FROM services
        CROSS JOIN compared_months
        LEFT JOIN filtered AS this_period
            ON this_period.service = services.service AND this_period.month = compared_months.this_month
        LEFT JOIN filtered AS previous_period
            ON previous_period.service = services.service AND previous_period.month = compared_months.previous_month
        LEFT JOIN filtered AS last_year_period
            ON last_year_period.service = services.service AND last_year_period.month = compared_months.same_month_last_year
        ORDER BY coalesce(this_period.revenue_cents, 0) DESC, services.service
    """), {"month": month, "location": location, "city": city})

    return [
        ServiceMonth(
            service=service,
            this_month=Period(jobs, revenue),
            previous_month=Period(previous_jobs, previous_revenue),
            same_month_last_year=Period(last_year_jobs, last_year_revenue),
        )
        for service, jobs, revenue, previous_jobs, previous_revenue, last_year_jobs, last_year_revenue in rows
    ]


def _relative_change(before: int, after: int) -> float | None:
    """+0.25 means 25% more. None when there was nothing before to compare against."""
    if before == 0:
        return None
    return (after - before) / before
