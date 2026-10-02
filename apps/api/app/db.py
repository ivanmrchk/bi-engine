from sqlalchemy import create_engine

from app.config import settings
from app.migrations import apply_pending_migrations

engine = create_engine(settings.database_url, pool_pre_ping=True)


def init_db() -> None:
    apply_pending_migrations(engine)
