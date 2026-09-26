"""Load every file under the raw data directory into the raw tables.

    python -m app.ingestion                 # uses RAW_DATA_DIR
    python -m app.ingestion --raw-dir PATH

Safe to run any number of times: files already stored are skipped.
Each file is stored in its own transaction, so one bad file is reported
and skipped without undoing the others.
"""

import argparse
from pathlib import Path

from sqlalchemy import Engine

from app.config import settings
from app.db import engine
from app.ingestion.feeds import FEEDS, Feed
from app.ingestion.raw_store import store_file


def load_feed_directory(engine: Engine, raw_dir: Path, feed: Feed) -> tuple[int, int, list[str]]:
    """(new files, already-stored files, failures) for one feed's folder."""
    new_files, known_files, failures = 0, 0, []
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
            known_files += 1
    return new_files, known_files, failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Load raw source files into the raw tables.")
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_data_dir,
                        help="folder containing the feeds' subfolders (default: %(default)s)")
    arguments = parser.parse_args()

    print(f"Loading raw files from {arguments.raw_dir}")
    for feed in FEEDS:
        new_files, known_files, failures = load_feed_directory(engine, arguments.raw_dir, feed)
        print(f"  {feed.name:28} {new_files:4} new, {known_files:4} already stored, {len(failures)} failed")
        for failure in failures:
            print(f"      ! {failure}")


if __name__ == "__main__":
    main()
