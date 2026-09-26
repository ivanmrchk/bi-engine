"""The company history as Housecall Pro's API would return it.

Mirrors the paginated `GET /jobs` and `GET /invoices` responses: money in
integer cents, timestamps in UTC, and customer details exactly as the
office typed them. Leads that never booked don't exist in Housecall Pro.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from synthetic_data.customers import Customer
from synthetic_data.jobs import CompanyHistory, Estimate, EstimateStatus, Job, Lead, LeadOutcome
from synthetic_data.sources.formats import (
    city_as_typed_by_a_person,
    phone_as_typed_by_a_person,
    utc_timestamp,
)

PAGE_SIZE = 200
FIRST_INVOICE_NUMBER = 1001
FIRST_ESTIMATE_NUMBER = 5001
SHARE_OF_INVOICES_LEFT_UNPAID = 0.06
SHARE_OF_RECORDS_WITH_LEAD_SOURCE_LEFT_BLANK = 0.45

# The office picks a lead source from a dropdown, when they remember to.
LEAD_SOURCE_AS_RECORDED_BY_OFFICE = {
    "google_business_profile": "Google",
    "organic_search": "Website",
    "google_ads": "Google Ads",
    "referral": "Referral",
    "chatgpt": "Website",
}

# How the office describes each kind of job when booking it.
JOB_DESCRIPTIONS = {
    "No-Power Troubleshooting": ("No power in part of house", "Half the house lost power", "Outlets dead - troubleshoot"),
    "Outlet & Switch Installation": ("Add outlets", "Replace switches and outlets", "Install new GFCI outlets"),
    "Light Fixture Installation": ("Install light fixtures", "Recessed lighting install", "Hang chandelier"),
    "Diagnostic Visit": ("Diagnose flickering lights", "Breaker keeps tripping", "Burning smell from outlet"),
    "EV Charger Installation": ("EV charger install", "Install Tesla wall connector", "Level 2 charger in garage"),
    "Panel Upgrade": ("Panel upgrade 200A", "Replace old Zinsco panel", "Service upgrade"),
    "Heated Floor Wiring": ("Wire heated floor in bathroom", "Floor heat thermostat + circuit"),
    "Commercial Electrical Work": ("Office lighting retrofit", "Tenant improvement wiring", "Restaurant circuit add"),
    "Generator Installation": ("Generator inlet + interlock", "Install standby generator", "Generator hookup"),
    "Hot Tub Wiring": ("Hot tub wiring", "Spa disconnect + 50A circuit"),
    "Circuit Breaker Replacement": ("Replace bad breaker", "Breaker replacement", "Swap AFCI breakers"),
}


@dataclass(frozen=True)
class HousecallProExport:
    job_pages: list[dict]
    invoice_pages: list[dict]
    estimate_pages: list[dict]


def export_housecall_pro(history: CompanyHistory, randomness: random.Random) -> HousecallProExport:
    job_records = []
    invoice_records = []

    for invoice_number, job in enumerate(history.jobs, start=FIRST_INVOICE_NUMBER):
        paid_at = _paid_at(job, randomness)
        job_records.append(_job_record(job, invoice_number, paid_at, randomness))
        if job.completed_at is not None:
            invoice_records.append(_invoice_record(job, invoice_number, paid_at, randomness))

    estimate_records = [
        _estimate_record(estimate, estimate_number, randomness)
        for estimate_number, estimate in enumerate(history.estimates, start=FIRST_ESTIMATE_NUMBER)
    ]

    return HousecallProExport(
        job_pages=_paginate(job_records, collection_name="jobs"),
        invoice_pages=_paginate(invoice_records, collection_name="invoices"),
        estimate_pages=_paginate(estimate_records, collection_name="estimates"),
    )


# --- Customers and addresses, as the office typed them --------------------


def _customer_record(customer: Customer, randomness: random.Random) -> dict:
    """Retyped on every job and estimate, so the same person's phone
    number can be formatted differently from one record to the next."""
    return {
        "id": customer.customer_id,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "email": customer.email,
        "mobile_number": phone_as_typed_by_a_person(customer.phone_numbers[0], randomness),
        "home_number": (
            phone_as_typed_by_a_person(customer.phone_numbers[1], randomness)
            if len(customer.phone_numbers) > 1
            else None
        ),
    }


def _address_record(customer: Customer, randomness: random.Random) -> dict:
    return {
        "street": customer.street_address,
        "city": city_as_typed_by_a_person(customer.service_area.city, randomness),
        "state": randomness.choices(("WA", "wa", "Wa", None), weights=(90, 5, 2, 3))[0],
        "zip": customer.zip_code,
        "country": "US",
    }


# --- Jobs ----------------------------------------------------------------


def _job_record(job: Job, invoice_number: int, paid_at: datetime | None, randomness: random.Random) -> dict:
    lead = job.lead
    customer = lead.customer
    outstanding_balance = 0 if paid_at else job.invoice_total_cents

    return {
        "id": job.job_id,
        "invoice_number": str(invoice_number),
        "description": _description(job, randomness),
        "customer": _customer_record(customer, randomness),
        "address": _address_record(customer, randomness),
        "work_status": _work_status(job, randomness),
        "schedule": {
            "scheduled_start": utc_timestamp(job.scheduled_start),
            "scheduled_end": utc_timestamp(job.scheduled_start + timedelta(hours=2)),
        },
        "work_timestamps": {
            "started_at": utc_timestamp(job.scheduled_start if job.completed_at else None),
            "completed_at": utc_timestamp(job.completed_at),
        },
        "total_amount": job.invoice_total_cents,
        "outstanding_balance": outstanding_balance,
        "lead_source": _lead_source(lead, randomness),
        "created_at": utc_timestamp(lead.created_at),
    }


def _description(job: Job, randomness: random.Random) -> str:
    description = randomness.choice(JOB_DESCRIPTIONS[job.lead.service.name])
    if job.lead.outcome is LeadOutcome.ESTIMATE_ONLY:
        return f"Estimate - {description}"
    return description


def _work_status(job: Job, randomness: random.Random) -> str:
    """Estimate-only visits are 'complete' too, which is why a status alone
    can't tell you whether the company was actually hired."""
    if job.lead.outcome is LeadOutcome.CANCELED:
        return randomness.choices(("user canceled", "pro canceled"), weights=(60, 40))[0]
    return randomness.choices(("complete unrated", "complete rated"), weights=(75, 25))[0]


def _lead_source(lead: Lead, randomness: random.Random) -> str | None:
    if randomness.random() < SHARE_OF_RECORDS_WITH_LEAD_SOURCE_LEFT_BLANK:
        return None
    return LEAD_SOURCE_AS_RECORDED_BY_OFFICE[lead.marketing_channel.name]


# --- Invoices ------------------------------------------------------------


def _paid_at(job: Job, randomness: random.Random) -> datetime | None:
    if job.completed_at is None or randomness.random() < SHARE_OF_INVOICES_LEFT_UNPAID:
        return None
    return job.completed_at + timedelta(days=randomness.randint(0, 10), hours=randomness.randint(1, 8))


def _invoice_record(job: Job, invoice_number: int, paid_at: datetime | None, randomness: random.Random) -> dict:
    return {
        "id": f"invoice_{invoice_number}",
        "job_id": job.job_id,
        "invoice_number": str(invoice_number),
        "status": "paid" if paid_at else "open",
        "amount": job.invoice_total_cents,
        "due_amount": 0 if paid_at else job.invoice_total_cents,
        "invoice_date": utc_timestamp(job.completed_at),
        "service_date": utc_timestamp(job.scheduled_start),
        "paid_at": utc_timestamp(paid_at),
        "items": _line_items(job, invoice_number, randomness),
    }


def _line_items(job: Job, invoice_number: int, randomness: random.Random) -> list[dict]:
    if job.lead.outcome is LeadOutcome.ESTIMATE_ONLY:
        return [_line_item(invoice_number, 1, "Service Call / Estimate", "labor", job.invoice_total_cents)]

    labor_cents = round(job.invoice_total_cents * randomness.uniform(0.55, 0.75))
    materials_cents = job.invoice_total_cents - labor_cents
    return [
        _line_item(invoice_number, 1, f"{job.lead.service.name} - Labor", "labor", labor_cents),
        _line_item(invoice_number, 2, "Materials", "material", materials_cents),
    ]


def _line_item(invoice_number: int, position: int, name: str, item_type: str, amount_cents: int) -> dict:
    return {"id": f"item_{invoice_number}_{position}", "name": name, "type": item_type, "amount": amount_cents}


# --- Estimates -----------------------------------------------------------


def _estimate_record(estimate: Estimate, estimate_number: int, randomness: random.Random) -> dict:
    """An estimate with a single option. Approval status is None while the
    customer hasn't answered, which is how 'no response' looks in HCP."""
    approval_status = None if estimate.status is EstimateStatus.NO_RESPONSE else str(estimate.status)
    lead = estimate.lead
    return {
        "id": estimate.estimate_id,
        "estimate_number": str(estimate_number),
        "customer": _customer_record(lead.customer, randomness),
        "address": _address_record(lead.customer, randomness),
        "options": [
            {
                "id": f"option_{estimate_number}_1",
                "name": randomness.choice(JOB_DESCRIPTIONS[lead.service.name]),
                "total_amount": estimate.quoted_total_cents,
                "approval_status": approval_status,
            }
        ],
        "lead_source": _lead_source(lead, randomness),
        "created_at": utc_timestamp(estimate.created_at),
    }


# --- Pagination ----------------------------------------------------------


def _paginate(records: list[dict], collection_name: str) -> list[dict]:
    """Split records into pages shaped like Housecall Pro's list responses."""
    chunks = [records[start : start + PAGE_SIZE] for start in range(0, len(records), PAGE_SIZE)]
    chunks = chunks or [[]]  # an empty collection is still one (empty) page
    return [
        {
            collection_name: chunk,
            "page": page_number,
            "page_size": PAGE_SIZE,
            "total_pages": len(chunks),
            "total_items": len(records),
        }
        for page_number, chunk in enumerate(chunks, start=1)
    ]
