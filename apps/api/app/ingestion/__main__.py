"""Load every file under the raw data directory into the raw tables.

    python -m app.ingestion                 # uses RAW_DATA_DIR
    python -m app.ingestion --raw-dir PATH

Safe to run any number of times: files already stored are skipped.
"""

import argparse
from pathlib import Path

from app.config import settings
from app.db import engine
from app.ingestion.raw_directory import load_raw_directory


def main() -> None:
    parser = argparse.ArgumentParser(description="Load raw source files into the raw tables.")
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_data_dir,
                        help="folder containing the feeds' subfolders (default: %(default)s)")
    arguments = parser.parse_args()

    print(f"Loading raw files from {arguments.raw_dir}")
    for result in load_raw_directory(engine, arguments.raw_dir):
        print(f"  {result.feed:28} {result.new_files:4} new, {result.already_stored:4} already stored, "
              f"{len(result.failures)} failed")
        for failure in result.failures:
            print(f"      ! {failure}")


if __name__ == "__main__":
    main()
