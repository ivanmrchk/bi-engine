from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.analysis.call_handling import CallHandlingMonth, call_handling_by_month
from app.analysis.channel_funnel import ChannelFunnelReport, channel_funnel
from app.analysis.city_diagnosis import LaggingCitiesReport, diagnose_cities
from app.analysis.hot_services import ServiceMonth, hot_services
from app.analysis.months import NotAMonth, add_months, parse_month
from app.db import engine

router = APIRouter()


@dataclass(frozen=True)
class HotServicesReport:
    month: str
    location: str | None
    city: str | None
    services: list[ServiceMonth]


@dataclass(frozen=True)
class AvailableMonths:
    first_month: str | None  # YYYY-MM
    last_month: str | None
    # The newest month is still in progress, so views open on the one before it.
    last_complete_month: str | None


@router.get("/months", response_model=AvailableMonths)
def get_available_months() -> AvailableMonths:
    """The first and last months with completed jobs, for month pickers."""
    with engine.connect() as connection:
        first, last = connection.execute(text("SELECT min(month), max(month) FROM analytics.service_months")).one()
    if first is None:
        return AvailableMonths(None, None, None)
    return AvailableMonths(
        first_month=f"{first:%Y-%m}",
        last_month=f"{last:%Y-%m}",
        last_complete_month=f"{add_months(last, -1):%Y-%m}",
    )


@router.get("/hot-services", response_model=HotServicesReport)
def get_hot_services(
    month: str = Query(..., description="YYYY-MM", examples=["2026-06"]),
    location: str | None = Query(None, description="Eastside or South Sound; all when left out"),
    city: str | None = Query(None, description="One city, e.g. Bellevue; all when left out"),
) -> HotServicesReport:
    """Services ranked by revenue, against last month and the same month last year."""
    first_day = _parse_month_or_422(month)
    with engine.connect() as connection:
        return HotServicesReport(month, location, city, hot_services(connection, first_day, location, city))


@router.get("/lagging-cities", response_model=LaggingCitiesReport)
def get_lagging_cities(
    month: str = Query(..., description="Last month of the period, YYYY-MM", examples=["2026-08"]),
    months: int = Query(6, ge=3, le=12, description="How many months the period spans"),
    location: str | None = Query(None, description="Eastside or South Sound; all when left out"),
) -> LaggingCitiesReport:
    """Each city's revenue against the same months a year before, and which
    factor clearly fell: demand, conversion, or ticket size."""
    last_month = _parse_month_or_422(month)
    with engine.connect() as connection:
        return diagnose_cities(connection, last_month, months, location)


@router.get("/channel-funnel", response_model=ChannelFunnelReport)
def get_channel_funnel(
    first_month: str = Query(..., description="YYYY-MM", examples=["2026-03"]),
    last_month: str = Query(..., description="YYYY-MM", examples=["2026-08"]),
    location: str | None = Query(None, description="Eastside or South Sound; all when left out"),
) -> ChannelFunnelReport:
    """Leads, booked jobs, real jobs, and revenue for each marketing channel."""
    first, last = _parse_month_range_or_422(first_month, last_month)
    with engine.connect() as connection:
        return channel_funnel(connection, first, last, location)


@router.get("/call-handling", response_model=list[CallHandlingMonth])
def get_call_handling(
    first_month: str = Query(..., description="YYYY-MM", examples=["2025-01"]),
    last_month: str = Query(..., description="YYYY-MM", examples=["2025-12"]),
    location: str | None = Query(None, description="Eastside or South Sound; all when left out"),
) -> list[CallHandlingMonth]:
    """Each month's lead and customer calls: who answered, how many went
    unanswered, and how fast the unanswered ones were called back."""
    first, last = _parse_month_range_or_422(first_month, last_month)
    with engine.connect() as connection:
        return call_handling_by_month(connection, first, last, location)


def _parse_month_range_or_422(first_month: str, last_month: str):
    first, last = _parse_month_or_422(first_month), _parse_month_or_422(last_month)
    if first > last:
        raise HTTPException(status_code=422, detail=f"{first_month} comes after {last_month}")
    return first, last


def _parse_month_or_422(month: str):
    try:
        return parse_month(month)
    except NotAMonth as error:
        raise HTTPException(status_code=422, detail=str(error))
