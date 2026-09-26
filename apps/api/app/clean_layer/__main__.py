"""Rebuild the clean tables from the raw layer.

    python -m app.clean_layer
"""

import time

from app.clean_layer.rebuild import clean_table_row_counts, rebuild_clean_layer
from app.db import engine


def main() -> None:
    started = time.monotonic()
    with engine.begin() as connection:
        rebuild_clean_layer(connection)
        row_counts = clean_table_row_counts(connection)

    print(f"Rebuilt the clean layer in {time.monotonic() - started:.1f}s")
    for table, row_count in row_counts.items():
        print(f"  clean.{table:24} {row_count:7} rows")


if __name__ == "__main__":
    main()
