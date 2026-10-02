"""The Qdrant index of clean.notes, and searching it.

Each note becomes a point: its embedding plus a payload of metadata (date,
city, service, location) that searches can filter on. A point's id is
derived from the note's id and text, so syncing only embeds notes that are
new or edited, and removes points whose note is gone. Qdrant is the cache.
"""

import uuid
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date

from qdrant_client import QdrantClient
from qdrant_client.models import (
    DatetimeRange,
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointIdsList,
    PointStruct,
    VectorParams,
)
from sqlalchemy import Connection, text

from app.config import settings
from app.rag.embeddings import EMBEDDING_DIMENSIONS, embed_texts

COLLECTION = "notes"
POINT_ID_NAMESPACE = uuid.UUID("6f1c2a52-5d0e-4a3e-9a51-3c9d1f0b7e21")  # any fixed UUID
FILTERABLE_FIELDS = {
    "kind": PayloadSchemaType.KEYWORD,
    "city": PayloadSchemaType.KEYWORD,
    "service": PayloadSchemaType.KEYWORD,
    "location": PayloadSchemaType.KEYWORD,
    "written_on": PayloadSchemaType.DATETIME,
}
POINTS_PER_UPSERT = 256
CANDIDATES_PER_RESULT = 5  # fetch extra, so collapsing identical notes still fills the results


@dataclass(frozen=True)
class IndexSync:
    embedded: int
    removed: int
    unchanged: int


@dataclass(frozen=True)
class SearchFilters:
    city: str | None = None
    service: str | None = None
    location: str | None = None
    written_from: date | None = None
    written_until: date | None = None


@dataclass(frozen=True)
class NoteMatch:
    note_id: str
    kind: str
    written_on: date
    city: str | None
    service: str | None
    body: str
    similarity: float  # cosine similarity: 1.0 is identical meaning
    times_written: int = 1  # how many notes among the closest candidates say exactly this


def qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


def sync_note_index(connection: Connection, client: QdrantClient) -> IndexSync:
    _ensure_collection(client)
    notes = connection.execute(text("""
        SELECT note_id, kind, written_on, location_name, city, service, job_id, body FROM clean.notes
    """)).mappings().all()
    notes_by_point_id = {point_id(note["note_id"], note["body"]): note for note in notes}
    indexed_ids = _existing_point_ids(client)

    notes_to_embed = [(id_, note) for id_, note in notes_by_point_id.items() if id_ not in indexed_ids]
    for start in range(0, len(notes_to_embed), POINTS_PER_UPSERT):
        batch = notes_to_embed[start : start + POINTS_PER_UPSERT]
        vectors = embed_texts([note["body"] for _, note in batch])
        client.upsert(
            collection_name=COLLECTION,
            points=[
                PointStruct(id=id_, vector=vector, payload=_payload(note))
                for (id_, note), vector in zip(batch, vectors)
            ],
        )

    stale_ids = list(indexed_ids - notes_by_point_id.keys())
    if stale_ids:
        client.delete(collection_name=COLLECTION, points_selector=PointIdsList(points=stale_ids))

    return IndexSync(
        embedded=len(notes_to_embed),
        removed=len(stale_ids),
        unchanged=len(notes_by_point_id) - len(notes_to_embed),
    )


def search_notes(client: QdrantClient, question: str, filters: SearchFilters, limit: int = 5) -> list[NoteMatch]:
    """The notes closest in meaning to the question, among those passing the filters.

    Technicians type the same sentence on many jobs. Identical texts are
    returned once, with how many times they were written, so repeats don't
    crowd out other notes; the repeat count is evidence in itself.
    """
    [question_vector] = embed_texts([question])
    response = client.query_points(
        collection_name=COLLECTION,
        query=question_vector,
        query_filter=search_filter(filters),
        limit=limit * CANDIDATES_PER_RESULT,
        with_payload=True,
    )

    best_match_by_text: dict[str, NoteMatch] = {}
    times_written = Counter()
    for point in response.points:  # closest first, so the first of each text is its best match
        body = point.payload["body"]
        times_written[body] += 1
        best_match_by_text.setdefault(body, _note_match(point))
    return [
        replace(match, times_written=times_written[body])
        for body, match in list(best_match_by_text.items())[:limit]
    ]


def _note_match(point) -> NoteMatch:
    return NoteMatch(
        note_id=point.payload["note_id"],
        kind=point.payload["kind"],
        written_on=date.fromisoformat(point.payload["written_on"][:10]),
        city=point.payload.get("city"),
        service=point.payload.get("service"),
        body=point.payload["body"],
        similarity=point.score,
    )


def point_id(note_id: str, body: str) -> str:
    """The same note with the same text always gets the same id; edited text gets a new one."""
    return str(uuid.uuid5(POINT_ID_NAMESPACE, f"{note_id}\n{body}"))


def search_filter(filters: SearchFilters) -> Filter | None:
    conditions = [
        FieldCondition(key=field, match=MatchValue(value=value))
        for field, value in (("city", filters.city), ("service", filters.service), ("location", filters.location))
        if value is not None
    ]
    if filters.written_from or filters.written_until:
        conditions.append(FieldCondition(key="written_on", range=DatetimeRange(
            gte=_as_datetime_text(filters.written_from) if filters.written_from else None,
            lte=_as_datetime_text(filters.written_until) if filters.written_until else None,
        )))
    return Filter(must=conditions) if conditions else None


def _ensure_collection(client: QdrantClient) -> None:
    if client.collection_exists(COLLECTION):
        return
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=EMBEDDING_DIMENSIONS, distance=Distance.COSINE),
    )
    for field, schema in FILTERABLE_FIELDS.items():
        client.create_payload_index(collection_name=COLLECTION, field_name=field, field_schema=schema)


def _existing_point_ids(client: QdrantClient) -> set[str]:
    ids, next_page = set(), None
    while True:
        points, next_page = client.scroll(
            collection_name=COLLECTION, limit=1000, offset=next_page, with_payload=False, with_vectors=False
        )
        ids.update(str(point.id) for point in points)
        if next_page is None:
            return ids


def _payload(note) -> dict:
    return {
        "note_id": note["note_id"],
        "kind": note["kind"],
        "written_on": _as_datetime_text(note["written_on"]),
        "location": note["location_name"],
        "city": note["city"],
        "service": note["service"],
        "job_id": note["job_id"],
        "body": note["body"],
    }


def _as_datetime_text(day: date) -> str:
    """Qdrant's datetime fields take RFC 3339 timestamps."""
    return f"{day.isoformat()}T00:00:00Z"
