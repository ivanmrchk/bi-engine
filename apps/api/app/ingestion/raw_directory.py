"""Loads every file under a raw data directory into the raw tables.

Each file is stored in its own transaction, so one bad file is reported
and skipped without undoing the others. Files already stored are skipped.
"""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine

from app.ingestion.feeds import FEEDS, Feed
from app.ingestion.raw_store import store_file


@dataclass(frozen=True)
class FeedLoadResult:
    feed: str
    new_files: int
    already_stored: int
    failures: tuple[str, ...]


def load_raw_directory(engine: Engine, raw_dir: Path) -> list[FeedLoadResult]:
    return [_load_feed(engine, raw_dir, feed) for feed in FEEDS]


def _load_feed(engine: Engine, raw_dir: Path, feed: Feed) -> FeedLoadResult:
    new_files, already_stored, failures = 0, 0, []
    for path in sorted((raw_dir / feed.folder).glob(feed.file_pattern)):
        try:
            with engine.begin() as connection:
                stored = store_file(connection, feed, path.name, path.read_bytes())
        except Exception as error:  # report and move on; the transaction already rolled back
            failures.append(f"{path.name}: {error}")
            continue
        if stored.was_new:
            new_files += 1
        else:
            already_stored += 1
    return FeedLoadResult(feed.name, new_files, already_stored, tuple(failures))
