"""Rebuilds every clean table from the raw layer, in one transaction.

The clean tables are emptied and refilled by the numbered .sql files in
sql/, in file-name order. Because it all happens in a single transaction,
anyone querying clean.* sees either the old tables or the new ones, never
a half-built state. A full rebuild is simpler than tracking what changed,
and at this data size it takes seconds.
"""

from pathlib import Path

from sqlalchemy import Connection, text

from app.sql_scripts import run_sql_script

REBUILD_SQL_DIR = Path(__file__).resolve().parent / "sql"


def rebuild_clean_layer(connection: Connection) -> None:
    _empty_clean_tables(connection)
    for sql_file in sorted(REBUILD_SQL_DIR.glob("*.sql")):
        run_sql_script(connection, sql_file.read_text(encoding="utf-8"))


def clean_table_row_counts(connection: Connection) -> dict[str, int]:
    return {
        table: connection.execute(text(f"SELECT count(*) FROM clean.{table}")).scalar_one()
        for table in _clean_table_names(connection)
    }


def _empty_clean_tables(connection: Connection) -> None:
    # Table names come from the catalog, never from user input, so building
    # this one statement from them is safe.
    tables = ", ".join(f"clean.{table}" for table in _clean_table_names(connection))
    connection.exec_driver_sql(f"TRUNCATE {tables}")


def _clean_table_names(connection: Connection) -> list[str]:
    return list(connection.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'clean' ORDER BY tablename")
    ).scalars())
