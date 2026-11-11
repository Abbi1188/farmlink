from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[2] is the project root
ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "FarmLink"
    database_url: str = f"sqlite:///{(ROOT_DIR / 'database' / 'farmlink.db').as_posix()}"
    secret_key: str = "change-this-secret-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["http://localhost:5000", "http://127.0.0.1:5000"]
    require_farm_approval: bool = True
    order_response_timeout_minutes: int = 30

    model_config = SettingsConfigDict(env_file=ROOT_DIR / "backend" / ".env", extra="ignore")


settings = Settings()
