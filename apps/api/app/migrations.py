"""Applies the numbered .sql files in migrations/ that haven't run yet.

Each file runs once, in its own transaction, in file-name order. The
`schema_migrations` table records which files have run, so calling this
on every startup is safe.

    python -m app.migrations
"""

from pathlib import Path

from sqlalchemy import Engine, text

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    file_name  TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def apply_pending_migrations(engine: Engine) -> list[str]:
    """Runs every migration not yet applied and returns their file names."""
    with engine.begin() as connection:
        connection.execute(text(CREATE_MIGRATIONS_TABLE))
        already_applied = set(connection.execute(text("SELECT file_name FROM schema_migrations")).scalars())

    newly_applied = []
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if migration.name in already_applied:
            continue
        with engine.begin() as connection:  # the file and its record commit together, or not at all
            connection.exec_driver_sql(migration.read_text(encoding="utf-8"))
            connection.execute(
                text("INSERT INTO schema_migrations (file_name) VALUES (:file_name)"),
                {"file_name": migration.name},
            )
        newly_applied.append(migration.name)
    return newly_applied


if __name__ == "__main__":
    from app.db import engine

    applied = apply_pending_migrations(engine)
    print("Applied:", ", ".join(applied) if applied else "nothing, already up to date")
