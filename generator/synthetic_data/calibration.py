"""The numbers that make the synthetic company feel real.

Everything here is data, not logic. The values are loosely calibrated
against a real Seattle-area electrical contractor, then deliberately
shifted so the fictional company is not a copy of the real one.
"""

from dataclasses import dataclass
from datetime import date

COMPANY_NAME = "Brightwire Electric"  # fictional

FIRST_MONTH = date(2023, 9, 1)
LAST_MONTH = date(2026, 8, 1)

# Company-wide demand by calendar month (1.0 = a normal month).
# Winter storms and cold snaps drive December and January; February is quiet.
MONTHLY_DEMAND_MULTIPLIER = {
    1: 1.25, 2: 0.80, 3: 0.95, 4: 1.00, 5: 1.00, 6: 1.00,
    7: 1.05, 8: 0.95, 9: 1.00, 10: 0.95, 11: 1.05, 12: 1.30,
}

# A service is this much more likely to be booked during its busiest months.
BUSY_SEASON_BOOST = 1.6

# Share of customers who give the company a second phone number
# (a spouse's cell, a landline). Calls from that number are harder to attribute.
SECOND_PHONE_SHARE = 0.15

# Share of leads that come from someone who has hired the company before.
RETURNING_CUSTOMER_SHARE = 0.20

# What eventually happens to a lead. Only "completed" leads count toward
# a location's jobs per month, so the generator creates more leads than jobs.
LEAD_OUTCOME_SHARES = {
    "lost": 0.30,           # never booked (price shopping, went elsewhere)
    "canceled": 0.10,       # booked, then canceled before the visit
    "estimate_only": 0.14,  # paid for the visit, declined the work
    "completed": 0.46,      # the work was done and invoiced
}

ESTIMATE_VISIT_FEE_DOLLARS = 99

# Share of lost leads that were sent a written estimate before going quiet.
# Big projects are quoted up front far more often than service calls.
LOST_LEAD_ESTIMATE_SHARE_FOR_BIG_PROJECTS = 0.50
LOST_LEAD_ESTIMATE_SHARE_FOR_SERVICE_CALLS = 0.10

# No real job is invoiced below this; smaller totals are estimate-only visits.
MINIMUM_JOB_TICKET_DOLLARS = 150


@dataclass(frozen=True)
class ServiceArea:
    """A city served by one of the company's locations."""

    city: str
    zip_codes: tuple[str, ...]
    phone_area_code: str
    share_of_location_customers: float


@dataclass(frozen=True)
class Location:
    """A shop with its own phone line and the cities it serves.

    Completed jobs per month grow linearly from the month the location
    opened (or the first simulated month) to the last simulated month.
    """

    name: str
    business_phone_number: str  # the line customers dial, E.164
    opened_month: date
    jobs_per_month_when_opened: float
    jobs_per_month_at_end: float
    service_areas: tuple[ServiceArea, ...]


@dataclass(frozen=True)
class Service:
    """A kind of job the company sells.

    Ticket prices follow a log-normal distribution: most jobs cost around
    the median, while a few large ones pull the average far above it.
    `ticket_price_spread` controls how long that expensive tail is.

    Big projects are quoted with a written estimate before the work is
    booked; service calls are usually priced on site.
    """

    name: str
    share_of_jobs: float
    median_ticket_dollars: int
    ticket_price_spread: float
    busiest_months: tuple[int, ...]
    is_big_project: bool = False


@dataclass(frozen=True)
class MarketingChannel:
    """How a lead found the company.

    Channel mix shifts over time, so each share is given at the start and
    the end of the three years and interpolated in between.
    """

    name: str
    share_at_start: float
    share_at_end: float
    phone_call_share: float  # the rest submit a web form


EASTSIDE = Location(
    name="Eastside",
    business_phone_number="+14255550100",
    opened_month=FIRST_MONTH,  # open long before the simulation starts
    jobs_per_month_when_opened=18,
    jobs_per_month_at_end=40,
    service_areas=(
        ServiceArea("Issaquah", ("98027", "98029"), "425", 0.31),
        ServiceArea("Sammamish", ("98074", "98075"), "425", 0.20),
        ServiceArea("Bellevue", ("98004", "98005", "98006", "98007", "98008"), "425", 0.12),
        ServiceArea("Renton", ("98055", "98056", "98058", "98059"), "425", 0.09),
        ServiceArea("Seattle", ("98103", "98105", "98107", "98115", "98117", "98118"), "206", 0.08),
        ServiceArea("Redmond", ("98052", "98053"), "425", 0.05),
        ServiceArea("Kirkland", ("98033", "98034"), "425", 0.04),
        ServiceArea("Snoqualmie", ("98065",), "425", 0.04),
        ServiceArea("North Bend", ("98045",), "425", 0.03),
        ServiceArea("Mercer Island", ("98040",), "206", 0.02),
        ServiceArea("Maple Valley", ("98038",), "425", 0.02),
    ),
)

SOUTH_SOUND = Location(
    name="South Sound",
    business_phone_number="+12535550100",
    opened_month=date(2026, 3, 1),  # the new location, still ramping up
    jobs_per_month_when_opened=3,
    jobs_per_month_at_end=14,
    service_areas=(
        ServiceArea("Kent", ("98030", "98031", "98032"), "253", 0.30),
        ServiceArea("Auburn", ("98001", "98002", "98092"), "253", 0.20),
        ServiceArea("Federal Way", ("98003", "98023"), "253", 0.20),
        ServiceArea("Tacoma", ("98402", "98405", "98406", "98407"), "253", 0.18),
        ServiceArea("Puyallup", ("98371", "98372", "98373", "98374", "98375"), "253", 0.12),
    ),
)

LOCATIONS = (EASTSIDE, SOUTH_SOUND)

MARKETING_CHANNELS = (
    MarketingChannel("google_business_profile", 0.38, 0.32, 0.80),
    MarketingChannel("organic_search", 0.27, 0.22, 0.50),
    MarketingChannel("google_ads", 0.15, 0.14, 0.60),
    MarketingChannel("referral", 0.20, 0.17, 0.90),
    MarketingChannel("chatgpt", 0.00, 0.15, 0.30),  # AI search arrives
)

SERVICES = (
    Service("No-Power Troubleshooting", 0.22, 1150, 0.75, (12, 1, 7)),
    Service("Outlet & Switch Installation", 0.16, 1100, 0.90, (4, 7)),
    Service("Light Fixture Installation", 0.12, 1400, 0.85, (5, 6)),
    Service("Diagnostic Visit", 0.12, 850, 0.80, (1, 3)),
    Service("EV Charger Installation", 0.08, 1900, 1.00, (5, 6, 9), is_big_project=True),
    Service("Panel Upgrade", 0.07, 6800, 0.70, (6, 8), is_big_project=True),
    Service("Heated Floor Wiring", 0.06, 2100, 0.90, (12, 1), is_big_project=True),
    Service("Commercial Electrical Work", 0.05, 1600, 0.90, (), is_big_project=True),
    Service("Generator Installation", 0.04, 3100, 0.40, (10, 11, 12), is_big_project=True),
    Service("Hot Tub Wiring", 0.04, 1800, 0.70, (4, 5), is_big_project=True),
    Service("Circuit Breaker Replacement", 0.04, 1400, 0.80, ()),
)
