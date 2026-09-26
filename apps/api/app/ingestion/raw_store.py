"""Stores a source file in the raw tables, exactly once.

The file's SHA-256 is recorded with a unique constraint, so storing the
same bytes again is a no-op: `was_new` comes back False and nothing else
is written. Everything happens on the caller's connection, so the caller
decides the transaction: one bad file never leaves half its rows behind.
"""

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import Connection, text

from app.ingestion.feeds import Feed, FileFormat
from app.ingestion.grasshopper_report import parse_grasshopper_report


@dataclass(frozen=True)
class StoredFile:
    file_name: str
    was_new: bool
    file_id: int | None  # None when the file had already been stored


def store_file(connection: Connection, feed: Feed, file_name: str, content: bytes) -> StoredFile:
    file_id = _register_file(connection, feed, file_name, content)
    if file_id is None:
        return StoredFile(file_name, was_new=False, file_id=None)

    if feed.file_format is FileFormat.JSON:
        _store_json_document(connection, file_id, content)
    else:
        _store_grasshopper_rows(connection, file_id, content)
    return StoredFile(file_name, was_new=True, file_id=file_id)


def _register_file(connection: Connection, feed: Feed, file_name: str, content: bytes) -> int | None:
    """The new file's id, or None if these exact bytes were stored before."""
    return connection.execute(
        text("""
            INSERT INTO raw.ingested_files (feed, file_name, content_sha256)
            VALUES (:feed, :file_name, :content_sha256)
            ON CONFLICT (feed, content_sha256) DO NOTHING
            RETURNING file_id
        """),
        {"feed": feed.name, "file_name": file_name, "content_sha256": hashlib.sha256(content).hexdigest()},
    ).scalar_one_or_none()


def _store_json_document(connection: Connection, file_id: int, content: bytes) -> None:
    """Postgres parses the JSON itself, so malformed files are rejected here."""
    connection.execute(
        text("INSERT INTO raw.json_documents (file_id, body) VALUES (:file_id, CAST(:body AS JSONB))"),
        {"file_id": file_id, "body": content.decode("utf-8")},
    )


def _store_grasshopper_rows(connection: Connection, file_id: int, content: bytes) -> None:
    # utf-8-sig drops the invisible byte-order mark Windows tools often put at the start.
    rows = parse_grasshopper_report(content.decode("utf-8-sig"))
    if not rows:  # a quiet week: the file is recorded, there are just no calls in it
        return
    connection.execute(
        text("""
            INSERT INTO raw.csv_rows (file_id, line_number, fields)
            VALUES (:file_id, :line_number, CAST(:fields AS JSONB))
        """),
        [
            {"file_id": file_id, "line_number": line_number, "fields": json.dumps(fields)}
            for line_number, fields in rows
        ],
    )
