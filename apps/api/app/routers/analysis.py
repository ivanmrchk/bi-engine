from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Query

from app.analysis.city_diagnosis import LaggingCitiesReport, diagnose_cities
from app.analysis.hot_services import ServiceMonth, hot_services
from app.analysis.months import NotAMonth, parse_month
from app.db import engine

router = APIRouter()


@dataclass(frozen=True)
class HotServicesReport:
    month: str
    location: str | None
    city: str | None
    services: list[ServiceMonth]


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


def _parse_month_or_422(month: str):
    try:
        return parse_month(month)
    except NotAMonth as error:
        raise HTTPException(status_code=422, detail=str(error))
