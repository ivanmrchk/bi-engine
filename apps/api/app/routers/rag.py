import hashlib
import uuid

from fastapi import APIRouter, Depends
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings
from app.schemas import RagDoc, RagQuery

router = APIRouter()
COLLECTION = "bi_engine_notes"
VECTOR_SIZE = 32


def get_qdrant() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


def ensure_collection(client: QdrantClient) -> None:
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def embed(text: str) -> list[float]:
    """Placeholder embedding function so the API runs with zero paid keys.

    Swap this for a real embeddings call (OpenAI text-embedding-3-small, or
    any local model) once you're ready — everything else in this router
    stays the same.
    """
    digest = hashlib.sha256(text.encode()).digest()
    return [b / 255 for b in digest[:VECTOR_SIZE]]


@router.post("/index")
def index_doc(doc: RagDoc, client: QdrantClient = Depends(get_qdrant)):
    ensure_collection(client)
    point_id = str(uuid.uuid4())
    client.upsert(
        collection_name=COLLECTION,
        points=[
            PointStruct(
                id=point_id,
                vector=embed(doc.text),
                payload={"text": doc.text, "location_id": doc.location_id},
            )
        ],
    )
    return {"id": point_id}


@router.post("/query")
def query_docs(q: RagQuery, client: QdrantClient = Depends(get_qdrant)):
    ensure_collection(client)
    hits = client.search(collection_name=COLLECTION, query_vector=embed(q.text), limit=q.top_k)
    return {
        "matches": [
            {"score": h.score, "text": h.payload.get("text"), "location_id": h.payload.get("location_id")}
            for h in hits
        ]
    }
