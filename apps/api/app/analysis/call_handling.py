"""How incoming calls were handled, month by month.

Counts the calls that matter to the business (leads and customers; not
spam, suppliers, or the company's own numbers): who answered, how many
went unanswered, and how quickly the owner called back the ones that did.
An unanswered lead call that is never returned is a lost opportunity.
"""

from datetime import date

from pydantic import computed_field
from pydantic.dataclasses import dataclass
from sqlalchemy import Connection, text

from app.analysis.months import add_months

CALLBACK_WINDOW_HOURS = 24


@dataclass(frozen=True)
class CallHandlingMonth:
    month: date
    calls: int
    answered_by_owner: int
    answered_by_ai: int
    voicemail: int
    missed: int
    unanswered_returned: int  # voicemail or missed, then called back within a day
    median_minutes_to_callback: float | None

    @computed_field
    @property
    def unanswered(self) -> int:
        return self.voicemail + self.missed

    @computed_field
    @property
    def unanswered_share(self) -> float | None:
        return self.unanswered / self.calls if self.calls else None

    @computed_field
    @property
    def never_returned(self) -> int:
        return self.unanswered - self.unanswered_returned


def call_handling_by_month(
    connection: Connection, first_month: date, last_month: date, location: str | None = None
) -> list[CallHandlingMonth]:
    rows = connection.execute(text("""
        WITH business_calls AS (
            SELECT
                call.*,
                date_trunc('month', call.started_at AT TIME ZONE 'America/Los_Angeles')::DATE AS month
            FROM clean.calls AS call
            WHERE call.direction = 'inbound'
              AND call.classification IN (
                  'new_customer_lead', 'returning_customer_lead', 'unconverted_caller',
                  'job_related', 'existing_customer_other'
              )
              AND (CAST(:location AS TEXT) IS NULL OR call.location_name = :location)
        ),
        with_callbacks AS (
            SELECT business_calls.*, callback.minutes_to_callback
            FROM business_calls
            LEFT JOIN LATERAL (
                SELECT extract(EPOCH FROM outbound.started_at - business_calls.started_at) / 60 AS minutes_to_callback
                FROM clean.calls AS outbound
                WHERE outbound.direction = 'outbound'
                  AND outbound.outside_number = business_calls.outside_number
                  AND outbound.started_at > business_calls.started_at
                  AND outbound.started_at <= business_calls.started_at + make_interval(hours => :callback_window_hours)
                ORDER BY outbound.started_at
                LIMIT 1
            ) AS callback ON business_calls.outcome IN ('missed', 'voicemail')
            WHERE business_calls.month BETWEEN :first_month AND :last_month
        )
        SELECT
            month,
            count(*) AS calls,
            count(*) FILTER (WHERE outcome = 'answered_by_owner') AS answered_by_owner,
            count(*) FILTER (WHERE outcome = 'answered_by_ai') AS answered_by_ai,
            count(*) FILTER (WHERE outcome = 'voicemail') AS voicemail,
            count(*) FILTER (WHERE outcome = 'missed') AS missed,
            count(minutes_to_callback) AS unanswered_returned,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY minutes_to_callback) AS median_minutes_to_callback
        FROM with_callbacks
        GROUP BY month
        ORDER BY month
    """), {
        "first_month": first_month,
        "last_month": last_month,
        "location": location,
        "callback_window_hours": CALLBACK_WINDOW_HOURS,
    }).mappings()
    return [CallHandlingMonth(**row) for row in rows]
