from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.migrations import apply_pending_migrations

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    apply_pending_migrations(engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
