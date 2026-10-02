"""The monthly brief: the month's numbers and notes, in plain English."""

from fastapi import APIRouter, HTTPException, Query

from app.analysis.months import NotAMonth, parse_month
from app.brief.service import Brief, write_brief
from app.db import engine
from app.rag.note_index import qdrant_client

router = APIRouter()


@router.get("", response_model=Brief)
def get_brief(
    month: str = Query(..., description="YYYY-MM", examples=["2026-08"]),
    location: str | None = Query(None, description="Eastside or South Sound; the whole company when left out"),
) -> Brief:
    """The month's brief, with the facts and notes it was written from.

    Every number in it comes from those facts or notes; `rejected_drafts`
    lists the numbers any discarded draft made up.
    """
    try:
        first_day = parse_month(month)
    except NotAMonth as error:
        raise HTTPException(status_code=422, detail=str(error))
    with engine.connect() as connection:
        return write_brief(connection, qdrant_client(), first_day, location)
