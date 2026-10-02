"""The facts a monthly brief may state, gathered from the analyses.

Every number is formatted here, once ('-42%', '$45,221'). The brief may
only copy numbers that appear in these facts or in the retrieved notes,
never compute new ones, which is what lets the guard check every number.
"""

from datetime import date

from pydantic.dataclasses import dataclass
from sqlalchemy import Connection

from app.analysis.call_handling import call_handling_by_month
from app.analysis.channel_funnel import channel_funnel
from app.analysis.city_diagnosis import diagnose_cities
from app.analysis.hot_services import hot_services
from app.analysis.months import add_months

TOP_SERVICES = 5
# Said outright, because a blank reads as "no change": a new location has no year before.
NOTHING_TO_COMPARE = "no comparison possible: no jobs in the same months a year before"
CITY_WINDOW_MONTHS = 6
CHANNEL_WINDOW_MONTHS = 3

# How each channel reads in a brief: the model copies whatever the facts say.
CHANNEL_NAMES = {
    "google_ads": "Google Ads",
    "google_business_profile": "Google Business Profile (tagged link)",
    "google_search_or_profile": "Google search or Business Profile (can't tell which)",
    "chatgpt": "ChatGPT",
    "referral": "referrals",
    "website_unspecified": "the website (source not recorded)",
    "unknown": "unknown (mostly phone calls, which carry no tracking)",
}


@dataclass(frozen=True)
class BriefFacts:
    month: date
    location: str | None
    sheet: dict  # what the brief may say, every number already formatted
    struggling_cities: list[tuple[str, list[str]]]  # (city, factors that clearly fell), worst first


def gather_facts(connection: Connection, month: date, location: str | None = None) -> BriefFacts:
    services = hot_services(connection, month, location)
    cities = diagnose_cities(connection, month, CITY_WINDOW_MONTHS, location)
    [calls] = call_handling_by_month(connection, month, month, location) or [None]
    funnel = channel_funnel(connection, add_months(month, -(CHANNEL_WINDOW_MONTHS - 1)), month, location)

    struggling = [city for city in cities.cities if city.reasons and (city.revenue_change or 0) < 0]
    sheet = {
        "month": f"{month:%B %Y}",
        "area": location or "the whole company",
        "top_services_this_month": [
            {
                "service": service.service,
                "jobs": service.this_month.jobs,
                "revenue": _dollars(service.this_month.revenue_cents),
                "change_vs_same_month_last_year": (
                    _percent_change(service.revenue_change_vs_last_year)
                    if service.has_enough_jobs_vs_last_year else "too few jobs to compare, so not evidence"
                ),
            }
            for service in services if service.this_month.jobs > 0
        ][:TOP_SERVICES],
        "revenue_vs_same_months_a_year_before": {
            "months_compared": CITY_WINDOW_MONTHS,
            "change": _percent_change(cities.company.revenue_change) or NOTHING_TO_COMPARE,
            "factor_changes": {factor.factor: _percent_change(factor.change) for factor in cities.company.factors},
            "factors_that_clearly_fell": cities.company.reasons,
        },
        "cities_with_clearly_falling_revenue": [
            {
                "city": city.city,
                "revenue_change": _percent_change(city.revenue_change),
                "factors_that_clearly_fell": city.reasons,
                "factor_changes": {factor.factor: _percent_change(factor.change) for factor in city.factors},
            }
            for city in struggling
        ],
        "calls_this_month": _call_facts(calls),
        "lead_channels": {
            "months_compared": CHANNEL_WINDOW_MONTHS,
            "channels": [
                {
                    "channel": CHANNEL_NAMES.get(channel.channel, channel.channel),
                    "leads": channel.leads,
                    "close_rate": (
                        "unreliable, only known for leads that booked" if channel.rates_are_inflated
                        else _percent(channel.close_rate)
                    ),
                }
                for channel in funnel.channels
            ],
        },
    }
    return BriefFacts(month, location, sheet, [(city.city, city.reasons) for city in struggling])


def _call_facts(calls) -> dict:
    if calls is None:
        return {"calls": 0}
    return {
        "calls_from_leads_and_customers": calls.calls,
        "answered_by_owner": calls.answered_by_owner,
        "answered_by_ai_call_taker": calls.answered_by_ai,
        "unanswered": calls.unanswered,
        "unanswered_share": _percent(calls.unanswered_share),
        "unanswered_then_called_back_within_a_day": calls.unanswered_returned,
        "unanswered_and_never_called_back": calls.never_returned,
        "median_minutes_to_call_back": (
            round(calls.median_minutes_to_callback) if calls.median_minutes_to_callback is not None else None
        ),
    }


def _dollars(cents: int) -> str:
    return f"${cents / 100:,.0f}"


def _percent(share: float | None) -> str | None:
    return None if share is None else f"{share:.0%}"


def _percent_change(change: float | None) -> str | None:
    return None if change is None else f"{change:+.0%}"
