from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.services import analysis as analysis_service

router = APIRouter()


@router.get("/hot-services")
def hot_services(month: str = Query(..., description="YYYY-MM"), session: Session = Depends(get_session)):
    return {"month": month, "services": analysis_service.hot_services(session, month)}


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
