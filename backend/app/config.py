from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[2] is the project root
ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "FarmBridge"
    database_url: str = f"sqlite:///{(ROOT_DIR / 'database' / 'farmlink.db').as_posix()}"
    secret_key: str = "change-this-secret-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["http://localhost:5000", "http://127.0.0.1:5000"]
    order_response_timeout_minutes: int = 30

    # Stock photos are saved here and served by the API under /uploads
    upload_dir: str = str(ROOT_DIR / "backend" / "uploads")
    max_stock_photos: int = 3
    max_photo_mb: int = 5

    # Registration OTP. While no SMS provider is connected, keep otp_debug_return=True so the
    # code is shown on screen. Set it to False in production once send_sms() really sends SMS.
    otp_debug_return: bool = True
    otp_expire_minutes: int = 5
    otp_resend_seconds: int = 30
    otp_max_attempts: int = 5

    # The one built-in admin account, created automatically on first start.
    admin_name: str = "Admin"
    admin_phone: str = "03000000000"
    admin_password: str = "admin123"

    model_config = SettingsConfigDict(env_file=ROOT_DIR / "backend" / ".env", extra="ignore")


settings = Settings()
