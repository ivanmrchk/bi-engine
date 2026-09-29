from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analysis.hot_services import ServiceMonth, hot_services
from app.analysis.months import NotAMonth, parse_month
from app.db import engine, get_session
from app.services import analysis as analysis_service

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
    try:
        first_day = parse_month(month)
    except NotAMonth as error:
        raise HTTPException(status_code=422, detail=str(error))
    with engine.connect() as connection:
        return HotServicesReport(month, location, city, hot_services(connection, first_day, location, city))


@router.get("/lagging-locations")
def lagging_locations(
    month: str = Query(..., description="YYYY-MM"),
    compare_to: str | None = Query(None, description="Defaults to the prior month"),
    session: Session = Depends(get_session),
):
    compare_to = compare_to or analysis_service.previous_month(month)
    return {
        "month": month,
        "compare_to": compare_to,
        "locations": analysis_service.lagging_locations(session, month, compare_to),
    }
