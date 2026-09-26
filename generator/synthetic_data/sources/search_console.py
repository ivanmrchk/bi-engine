"""Google Search Console data, as the Search Analytics API returns it.

POST /webmasters/v3/sites/{site}/searchAnalytics/query, requested one day
at a time, twice: once by date alone (the day's full totals) and once by
query and page. The second response leaves out rare "anonymized" queries,
so its rows never add up to the first one's totals.

Search Console keeps only 16 months of history. Anything older exists only
if someone saved it at the time, so that is all this export contains.
"""

import math
import random
from dataclasses import dataclass
from datetime import date

from synthetic_data.calibration import (
    BUSY_SEASON_BOOST,
    COMPANY_WEBSITE,
    FIRST_MONTH,
    LAST_MONTH,
    LOCATIONS,
    SERVICES,
    Location,
    Service,
)
from synthetic_data.sources.formats import url_slug
from synthetic_data.timeline import add_months, blend, progress_since, simulated_days

SEARCH_CONSOLE_KEEPS_MONTHS = 16

# Roughly how many times a day the site appeared in Google results at the start.
DAILY_IMPRESSIONS_SCALE = 380

# Search demand grows over the three years; EV charger searches grow much
# faster than the company's EV jobs do. That gap is a planted opportunity.
SEARCH_DEMAND_GROWTH = 1.2
SEARCH_DEMAND_GROWTH_BY_SERVICE = {"EV Charger Installation": 1.9}

# How much searching happens in each location's market, relative to the Eastside.
MARKET_SIZE_BY_LOCATION = {"Eastside": 1.0, "South Sound": 0.7}

# Share of a service's searches that name a city ("panel upgrade bellevue")
# versus general ones ("panel upgrade near me", "panel upgrade").
CITY_SEARCH_SHARE = 0.6

# Where each kind of page ranks once the site's SEO has matured.
BEST_POSITION_FOR_CITY_PAGE = 5.0
BEST_POSITION_FOR_SERVICE_PAGE = 11.0
BEST_POSITION_FOR_NEAR_ME = 14.0
BEST_POSITION_FOR_BRAND = 1.1
# Pages start out ranking this many times worse, then improve steadily.
NEW_PAGE_POSITION_PENALTY = 1.6

BRAND_QUERIES = ("brightwire electric", "brightwire electric reviews")
BRAND_SHARE_OF_DEMAND = 0.04

# Rows with very few impressions are sometimes withheld for privacy.
ANONYMIZED_MAX_IMPRESSIONS = 2
ANONYMIZED_SHARE_OF_RARE_ROWS = 0.35

SEARCH_PHRASES = {
    "No-Power Troubleshooting": ("electrician no power", "power outage in house electrician"),
    "Outlet & Switch Installation": ("outlet installation", "electrician to add outlets"),
    "Light Fixture Installation": ("recessed lighting installation", "light fixture installation"),
    "Diagnostic Visit": ("electrician flickering lights", "breaker keeps tripping"),
    "EV Charger Installation": ("ev charger installation", "tesla charger installer"),
    "Panel Upgrade": ("electrical panel upgrade", "200 amp panel upgrade cost"),
    "Heated Floor Wiring": ("heated floor installation electrician", "radiant floor heat wiring"),
    "Commercial Electrical Work": ("commercial electrician", "commercial lighting retrofit"),
    "Generator Installation": ("generator installation", "generator interlock kit install"),
    "Hot Tub Wiring": ("hot tub wiring", "hot tub electrical hookup"),
    "Circuit Breaker Replacement": ("breaker replacement", "replace circuit breaker cost"),
}


@dataclass(frozen=True)
class SearchConsoleDay:
    day: date
    totals_response: dict  # dimensions: ["date"]
    query_page_response: dict  # dimensions: ["query", "page"]


@dataclass(frozen=True)
class _TrackedQuery:
    """A search the site shows up for, and the page Google shows for it."""

    query: str
    page_path: str
    share_of_demand: float
    best_position: float
    service: Service | None = None  # None for brand searches
    location: Location | None = None  # None for searches that name no city


@dataclass(frozen=True)
class _Row:
    query: str
    page_path: str
    clicks: int
    impressions: int
    position: float


def export_search_console(randomness: random.Random) -> list[SearchConsoleDay]:
    tracked_queries = _tracked_queries()
    first_available_day = _first_day_search_console_still_has()
    return [
        _search_console_day(day, tracked_queries, randomness)
        for day in simulated_days()
        if day >= first_available_day
    ]


def _first_day_search_console_still_has() -> date:
    """16 months of history, counting the last simulated month itself."""
    return add_months(LAST_MONTH, -(SEARCH_CONSOLE_KEEPS_MONTHS - 1))


# --- Which searches the site appears for ---------------------------------


def _tracked_queries() -> list[_TrackedQuery]:
    queries = [
        _TrackedQuery(query, "/", BRAND_SHARE_OF_DEMAND, BEST_POSITION_FOR_BRAND)
        for query in BRAND_QUERIES
    ]
    for service in SERVICES:
        phrases = SEARCH_PHRASES[service.name]
        demand_per_phrase = service.share_of_jobs / len(phrases)
        service_page = f"/{url_slug(service.name)}/"

        for phrase in phrases:
            general_demand = demand_per_phrase * (1 - CITY_SEARCH_SHARE) / 2
            queries.append(_TrackedQuery(phrase, service_page, general_demand, BEST_POSITION_FOR_SERVICE_PAGE, service))
            queries.append(_TrackedQuery(f"{phrase} near me", service_page, general_demand, BEST_POSITION_FOR_NEAR_ME, service))

            for location in LOCATIONS:
                for area in location.service_areas:
                    city_demand = (
                        demand_per_phrase
                        * CITY_SEARCH_SHARE
                        * MARKET_SIZE_BY_LOCATION[location.name]
                        * area.share_of_location_customers
                    )
                    queries.append(_TrackedQuery(
                        query=f"{phrase} {area.city.lower()}",
                        page_path=f"/{url_slug(service.name)}-{url_slug(area.city)}-wa/",
                        share_of_demand=city_demand,
                        best_position=BEST_POSITION_FOR_CITY_PAGE,
                        service=service,
                        location=location,
                    ))
    return queries


# --- One day of search activity ------------------------------------------


def _search_console_day(day: date, tracked_queries: list[_TrackedQuery], randomness: random.Random) -> SearchConsoleDay:
    rows = [row for query in tracked_queries if (row := _row_for(query, day, randomness)) is not None]
    visible_rows = [row for row in rows if not _is_anonymized(row, randomness)]
    visible_rows.sort(key=lambda row: (row.clicks, row.impressions), reverse=True)

    day_key = day.isoformat()
    totals_response = {
        "rows": [_response_row([day_key], rows)] if rows else [],
        "responseAggregationType": "byProperty",
    }
    query_page_response = {
        "rows": [
            _response_row([row.query, f"{COMPANY_WEBSITE}{row.page_path}"], [row])
            for row in visible_rows
        ],
        "responseAggregationType": "byPage",
    }
    return SearchConsoleDay(day, totals_response, query_page_response)


def _row_for(query: _TrackedQuery, day: date, randomness: random.Random) -> _Row | None:
    """How this search performed today, or None if the site never appeared."""
    pages_went_live = query.location.opened_month if query.location else FIRST_MONTH
    if day < pages_went_live:
        return None

    expected_impressions = DAILY_IMPRESSIONS_SCALE * query.share_of_demand * _demand_multiplier(query.service, day)
    impressions = _poisson(expected_impressions, randomness)
    if impressions == 0:
        return None

    position = _average_position(query, day, pages_went_live, randomness)
    clicks = randomness.binomialvariate(impressions, _click_through_rate(position))
    return _Row(query.query, query.page_path, clicks, impressions, position)


def _demand_multiplier(service: Service | None, day: date) -> float:
    month = day.replace(day=1)
    if service is None:
        return blend(1.0, SEARCH_DEMAND_GROWTH, progress_since(FIRST_MONTH, month))
    growth_by_the_end = SEARCH_DEMAND_GROWTH_BY_SERVICE.get(service.name, SEARCH_DEMAND_GROWTH)
    growth = blend(1.0, growth_by_the_end, progress_since(FIRST_MONTH, month))
    season = BUSY_SEASON_BOOST if day.month in service.busiest_months else 1.0
    return growth * season


def _average_position(query: _TrackedQuery, day: date, pages_went_live: date, randomness: random.Random) -> float:
    """New pages rank poorly and climb as they age; every day wobbles a little."""
    maturity = progress_since(pages_went_live, day.replace(day=1))
    trend = query.best_position * blend(NEW_PAGE_POSITION_PENALTY, 1.0, maturity)
    return max(1.0, trend * randomness.uniform(0.85, 1.15))


def _click_through_rate(position: float) -> float:
    """Clicks fall off steeply as a result moves down the page."""
    return min(0.6, 0.32 / position**0.9)


def _is_anonymized(row: _Row, randomness: random.Random) -> bool:
    return row.impressions <= ANONYMIZED_MAX_IMPRESSIONS and randomness.random() < ANONYMIZED_SHARE_OF_RARE_ROWS


def _response_row(keys: list[str], rows: list[_Row]) -> dict:
    """One API row. Position is averaged per impression, as Search Console does."""
    clicks = sum(row.clicks for row in rows)
    impressions = sum(row.impressions for row in rows)
    position = sum(row.position * row.impressions for row in rows) / impressions
    return {
        "keys": keys,
        "clicks": clicks,
        "impressions": impressions,
        "ctr": clicks / impressions,
        "position": position,
    }


def _poisson(expected: float, randomness: random.Random) -> int:
    """How many times something happened, when it happens `expected` times on average.

    Multiplies uniform random numbers until the product drops below
    e^-expected (Knuth's method). For large averages a bell curve is close
    enough and much faster.
    """
    if expected > 30:
        return max(0, round(randomness.gauss(expected, math.sqrt(expected))))
    threshold = math.exp(-expected)
    count = 0
    product = randomness.random()
    while product > threshold:
        count += 1
        product *= randomness.random()
    return count
