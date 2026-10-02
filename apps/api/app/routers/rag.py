"""Searching what people wrote: technicians' job notes and the owner's monthly notes."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.db import engine
from app.rag.embeddings import EmbeddingsUnavailable
from app.rag.note_index import IndexSync, NoteMatch, SearchFilters, qdrant_client, search_notes, sync_note_index

router = APIRouter()


@router.post("/index", response_model=IndexSync)
def index_notes() -> IndexSync:
    """Embed new or edited notes into the search index and drop removed ones."""
    try:
        with engine.connect() as connection:
            return sync_note_index(connection, qdrant_client())
    except EmbeddingsUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error))


@router.get("/search", response_model=list[NoteMatch])
def search(
    q: str = Query(..., min_length=3, description="What to look for, in plain words",
                   examples=["why are we losing jobs in Bellevue"]),
    kind: str | None = Query(None, description="job_note or owner_note"),
    city: str | None = Query(None, examples=["Bellevue"]),
    service: str | None = Query(None, examples=["Panel Upgrade"]),
    location: str | None = Query(None, description="Eastside or South Sound"),
    written_from: date | None = Query(None, description="YYYY-MM-DD"),
    written_until: date | None = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(5, ge=1, le=20),
) -> list[NoteMatch]:
    """The notes closest in meaning to `q`, optionally narrowed by kind, city, service, location, or date."""
    filters = SearchFilters(
        kind=kind,
        city=city,
        service=service,
        location=location,
        written_from=written_from,
        written_until=written_until,
    )
    try:
        return search_notes(qdrant_client(), q, filters, limit)
    except EmbeddingsUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error))
