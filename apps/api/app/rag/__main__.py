"""Bring the Qdrant note index in line with clean.notes.

    python -m app.rag

Only new or edited notes are embedded, so re-running costs nothing.
"""

from app.db import engine
from app.rag.note_index import qdrant_client, sync_note_index


def main() -> None:
    with engine.connect() as connection:
        result = sync_note_index(connection, qdrant_client())
    print(f"Note index: {result.embedded} embedded, {result.removed} removed, {result.unchanged} unchanged")


if __name__ == "__main__":
    main()
