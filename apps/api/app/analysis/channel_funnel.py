"""Leads to revenue, by marketing channel.

A lead is booked when it became a job, and closed when that job was real
work. Channels rest on evidence of differing strength (see clean.leads);
'unknown' is mostly phone calls, which carry no tracking at all.
"""

from datetime import date

from pydantic import computed_field
from pydantic.dataclasses import dataclass
from sqlalchemy import Connection, text

from app.analysis.months import add_months

ALL_CHANNELS = "all_channels"


@dataclass(frozen=True)
class ChannelFunnel:
    channel: str
    leads: int
    phone_leads: int
    web_leads: int
    booked_jobs: int
    real_jobs: int
    revenue_cents: int
    channel_from_office_dropdown: int  # leads whose channel came from the office's HCP lead source

    @computed_field
    @property
    def rates_are_inflated(self) -> bool:
        """The office's dropdown only exists on leads that became jobs, so a
        channel known that way never shows its lost leads: they all land in
        'unknown'. Its booking and close rates look better than they are."""
        return self.channel_from_office_dropdown > 0

    @computed_field
    @property
    def booking_rate(self) -> float | None:
        """Share of leads that became a job in Housecall Pro."""
        return self.booked_jobs / self.leads if self.leads else None

    @computed_field
    @property
    def close_rate(self) -> float | None:
        """Share of leads that became real, paid work."""
        return self.real_jobs / self.leads if self.leads else None

    @computed_field
    @property
    def revenue_per_lead_cents(self) -> int | None:
        return round(self.revenue_cents / self.leads) if self.leads else None


@dataclass(frozen=True)
class ChannelFunnelReport:
    first_month: date
    last_month: date
    location: str | None
    all_channels: ChannelFunnel
    channels: list[ChannelFunnel]  # most leads first


def channel_funnel(
    connection: Connection, first_month: date, last_month: date, location: str | None = None
) -> ChannelFunnelReport:
    rows = connection.execute(text("""
        SELECT
            coalesce(lead.channel, :all_channels) AS channel,
            count(*) AS leads,
            count(*) FILTER (WHERE lead.contact_method = 'phone_call') AS phone_leads,
            count(*) FILTER (WHERE lead.contact_method = 'web_form') AS web_leads,
            count(job.job_id) AS booked_jobs,
            count(*) FILTER (WHERE job.is_real_job) AS real_jobs,
            coalesce(sum(job.total_cents) FILTER (WHERE job.is_real_job), 0) AS revenue_cents,
            count(*) FILTER (WHERE lead.channel_evidence = 'office_lead_source') AS channel_from_office_dropdown
        FROM clean.leads AS lead
        LEFT JOIN clean.jobs AS job USING (job_id)
        WHERE (lead.contacted_at AT TIME ZONE 'America/Los_Angeles') >= :first_month
          AND (lead.contacted_at AT TIME ZONE 'America/Los_Angeles') < :month_after_last
          AND (CAST(:location AS TEXT) IS NULL OR lead.location_name = :location)
        GROUP BY GROUPING SETS ((lead.channel), ())
    """), {
        "first_month": first_month,
        "month_after_last": add_months(last_month, 1),
        "location": location,
        "all_channels": ALL_CHANNELS,
    }).mappings()

    funnels = [ChannelFunnel(**row) for row in rows]
    total = next(
        (funnel for funnel in funnels if funnel.channel == ALL_CHANNELS),
        ChannelFunnel(ALL_CHANNELS, 0, 0, 0, 0, 0, 0, 0),
    )
    channels = sorted(
        (funnel for funnel in funnels if funnel.channel != ALL_CHANNELS),
        key=lambda funnel: (-funnel.leads, funnel.channel),
    )
    return ChannelFunnelReport(first_month, last_month, location, total, channels)
