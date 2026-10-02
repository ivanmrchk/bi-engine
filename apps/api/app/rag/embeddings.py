"""Text to vectors with OpenAI's embedding model.

An embedding places a text as a point in a 1,536-dimensional space, where
texts that mean similar things land close together, even when they share
no words ("went with a cheaper competitor" and "lost the bid on price").
"""

from openai import OpenAI

from app.config import settings

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
TEXTS_PER_REQUEST = 256  # well under the API's per-request limit


class EmbeddingsUnavailable(RuntimeError):
    pass


def embed_texts(texts: list[str]) -> list[list[float]]:
    """One vector per text, in the same order."""
    if not settings.openai_api_key:
        raise EmbeddingsUnavailable("OPENAI_API_KEY is not set, so notes can't be embedded or searched")

    client = OpenAI(api_key=settings.openai_api_key)
    vectors = []
    for start in range(0, len(texts), TEXTS_PER_REQUEST):
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts[start : start + TEXTS_PER_REQUEST])
        vectors.extend(item.embedding for item in sorted(response.data, key=lambda item: item.index))
    return vectors
