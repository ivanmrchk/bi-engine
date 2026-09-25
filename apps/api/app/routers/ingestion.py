import json

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import EventIn, EventOut

router = APIRouter()


@router.post("", response_model=EventOut)
def ingest_event(event: EventIn, session: Session = Depends(get_session)):
    result = session.execute(
        text(
            """
            INSERT INTO events (source, location_id, event_type, payload, occurred_at)
            VALUES (:source, :location_id, :event_type, :payload, COALESCE(:occurred_at, now()))
            RETURNING id, occurred_at
            """
        ),
        {
            "source": event.source,
            "location_id": event.location_id,
            "event_type": event.event_type,
            "payload": json.dumps(event.payload),
            "occurred_at": event.occurred_at,
        },
    )
    row = result.fetchone()
    session.commit()
    return {"id": row.id, "occurred_at": row.occurred_at}
