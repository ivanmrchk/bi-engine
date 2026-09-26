"""What actually happened: leads, and the jobs that came out of them.

Every lead is someone asking for work. Most become a job in Housecall Pro;
some of those jobs are canceled or end as a paid estimate, and the rest are
completed and invoiced. Like customers.py, this is the *truth* that each
data source later reports in its own imperfect way.
"""

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import count

from synthetic_data.calibration import (
    BUSY_SEASON_BOOST,
    ESTIMATE_VISIT_FEE_DOLLARS,
    LEAD_OUTCOME_SHARES,
    LOCATIONS,
    MARKETING_CHANNELS,
    MINIMUM_JOB_TICKET_DOLLARS,
    MONTHLY_DEMAND_MULTIPLIER,
    RETURNING_CUSTOMER_SHARE,
    SERVICES,
    Location,
    MarketingChannel,
    Service,
)
from synthetic_data.customers import Customer, CustomerFactory
from synthetic_data.timeline import (
    blend,
    progress_since,
    progress_through_history,
    random_moment_in_month,
    simulated_months,
)


class ContactMethod(StrEnum):
    PHONE_CALL = "phone_call"
    WEB_FORM = "web_form"


class LeadOutcome(StrEnum):
    LOST = "lost"
    CANCELED = "canceled"
    ESTIMATE_ONLY = "estimate_only"
    COMPLETED = "completed"


@dataclass(frozen=True)
class Lead:
    lead_id: str
    customer: Customer
    service: Service
    marketing_channel: MarketingChannel
    contact_method: ContactMethod
    created_at: datetime
    outcome: LeadOutcome


@dataclass(frozen=True)
class Job:
    job_id: str
    lead: Lead
    scheduled_start: datetime
    completed_at: datetime | None  # None when the job was canceled
    invoice_total_cents: int  # 0 when the job was canceled


@dataclass(frozen=True)
class CompanyHistory:
    customers: tuple[Customer, ...]
    leads: tuple[Lead, ...]
    jobs: tuple[Job, ...]


class CompanyHistoryGenerator:
    """Simulates every lead and job, month by month."""

    def __init__(self, randomness: random.Random, customer_factory: CustomerFactory):
        self._randomness = randomness
        self._customer_factory = customer_factory

    def generate(self) -> CompanyHistory:
        self._customers_by_location: dict[str, list[Customer]] = {
            location.name: [] for location in LOCATIONS
        }
        self._next_lead_number = count(start=1)
        self._next_job_number = count(start=1)
        leads: list[Lead] = []
        jobs: list[Job] = []

        for month in simulated_months():
            for location in LOCATIONS:
                if month < location.opened_month:
                    continue
                for _ in range(self._lead_count_for(location, month)):
                    lead = self._create_lead(location, month)
                    leads.append(lead)
                    if lead.outcome is not LeadOutcome.LOST:
                        jobs.append(self._create_job(lead))

        all_customers = [
            customer
            for location_customers in self._customers_by_location.values()
            for customer in location_customers
        ]
        return CompanyHistory(tuple(all_customers), tuple(leads), tuple(jobs))

    # --- How many leads, and what kind -----------------------------------

    def _lead_count_for(self, location: Location, month) -> int:
        progress = progress_since(location.opened_month, month)
        expected_jobs = blend(location.jobs_per_month_when_opened, location.jobs_per_month_at_end, progress)
        expected_jobs *= MONTHLY_DEMAND_MULTIPLIER[month.month]
        expected_leads = expected_jobs / LEAD_OUTCOME_SHARES[LeadOutcome.COMPLETED]
        return round(expected_leads * self._randomness.uniform(0.9, 1.1))

    def _create_lead(self, location: Location, month) -> Lead:
        marketing_channel = self._pick_marketing_channel(month)
        return Lead(
            lead_id=f"lead_{next(self._next_lead_number):05d}",
            customer=self._pick_customer(location),
            service=self._pick_service(month),
            marketing_channel=marketing_channel,
            contact_method=self._pick_contact_method(marketing_channel),
            created_at=random_moment_in_month(month, self._randomness),
            outcome=self._pick_outcome(),
        )

    def _pick_customer(self, location: Location) -> Customer:
        location_customers = self._customers_by_location[location.name]
        if location_customers and self._randomness.random() < RETURNING_CUSTOMER_SHARE:
            return self._randomness.choice(location_customers)
        new_customer = self._customer_factory.create_customer(location)
        location_customers.append(new_customer)
        return new_customer

    def _pick_service(self, month) -> Service:
        weights = [
            service.share_of_jobs * (BUSY_SEASON_BOOST if month.month in service.busiest_months else 1)
            for service in SERVICES
        ]
        return self._randomness.choices(SERVICES, weights=weights)[0]

    def _pick_marketing_channel(self, month) -> MarketingChannel:
        progress = progress_through_history(month)
        weights = [
            blend(channel.share_at_start, channel.share_at_end, progress)
            for channel in MARKETING_CHANNELS
        ]
        return self._randomness.choices(MARKETING_CHANNELS, weights=weights)[0]

    def _pick_contact_method(self, marketing_channel: MarketingChannel) -> ContactMethod:
        if self._randomness.random() < marketing_channel.phone_call_share:
            return ContactMethod.PHONE_CALL
        return ContactMethod.WEB_FORM

    def _pick_outcome(self) -> LeadOutcome:
        outcomes = list(LeadOutcome)
        weights = [LEAD_OUTCOME_SHARES[outcome] for outcome in outcomes]
        return self._randomness.choices(outcomes, weights=weights)[0]

    # --- What happened on the job ----------------------------------------

    def _create_job(self, lead: Lead) -> Job:
        job_id = f"job_{next(self._next_job_number):05d}"
        scheduled_start = self._visit_time_after(lead.created_at)

        if lead.outcome is LeadOutcome.CANCELED:
            return Job(job_id, lead, scheduled_start, completed_at=None, invoice_total_cents=0)

        visit_length = timedelta(hours=self._randomness.randint(1, 6))
        if lead.outcome is LeadOutcome.ESTIMATE_ONLY:
            invoice_total_cents = ESTIMATE_VISIT_FEE_DOLLARS * 100
        else:
            invoice_total_cents = self._ticket_price_cents(lead.service)

        return Job(job_id, lead, scheduled_start, scheduled_start + visit_length, invoice_total_cents)

    def _visit_time_after(self, lead_created_at: datetime) -> datetime:
        """Visits are booked 1-7 days out, starting on the hour or half hour."""
        visit_day = lead_created_at + timedelta(days=self._randomness.randint(1, 7))
        return visit_day.replace(
            hour=self._randomness.randint(8, 15),
            minute=self._randomness.choice((0, 30)),
        )

    def _ticket_price_cents(self, service: Service) -> int:
        """A log-normal price: usually near the median, occasionally far above it."""
        price_dollars = self._randomness.lognormvariate(
            mu=math.log(service.median_ticket_dollars),
            sigma=service.ticket_price_spread,
        )
        return round(max(price_dollars, MINIMUM_JOB_TICKET_DOLLARS) * 100)
