from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.services import analysis as analysis_service
from app.services.llm import generate_brief

router = APIRouter()


@router.get("/{location_id}")
def location_brief(location_id: str, month: str = Query(..., description="YYYY-MM"), session: Session = Depends(get_session)):
    hot = analysis_service.hot_services(session, month)
    lagging = analysis_service.lagging_locations(session, month, analysis_service.previous_month(month))
    brief = generate_brief(location_id, month, hot, lagging)
    return {"location_id": location_id, "month": month, "brief": brief}
