from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EventIn(BaseModel):
    source: str
    location_id: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime | None = None


class EventOut(BaseModel):
    id: int
    occurred_at: datetime


class RagDoc(BaseModel):
    location_id: str
    text: str


class RagQuery(BaseModel):
    text: str
    top_k: int = 5
