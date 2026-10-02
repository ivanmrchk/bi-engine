from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Defaults suit running on the host against docker compose (Postgres on host port 5434).
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5434/bi_engine"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    openai_api_key: str | None = None
    # A dated snapshot, so briefs don't change because the model behind an alias did.
    brief_model: str = "gpt-5.4-mini-2026-03-17"
    allowed_origins: list[str] = ["http://localhost:8080", "http://localhost:5173"]
    raw_data_dir: Path = Path("/data/raw")  # where docker compose mounts ./data/raw

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


settings = Settings()
