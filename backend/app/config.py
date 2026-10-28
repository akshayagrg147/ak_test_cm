from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://localhost:55432/talkocrm"
    environment: str = "development"
    secret_key: str = "development-only-change-this-before-production-123456789"
    encryption_key: str = ""
    public_origin: str = "http://localhost:5173"
    storage_path: Path = Path(".local/storage")
    brand_name: str = "ViaCRM"
    contact_email: str = ""
    contact_phone: str = ""
    business_text: str = "CRM software shaped around the way you work."
    access_minutes: int = 15
    refresh_days: int = 14
    max_upload: int = 10 * 1024 * 1024
    max_recording_upload: int = 64 * 1024 * 1024

    def validate_production(self):
        if self.environment == "production":
            if len(self.secret_key) < 40 or "development" in self.secret_key:
                raise RuntimeError("Set a unique SECRET_KEY of at least 40 characters")
            if not self.encryption_key or not self.public_origin.startswith("https://"):
                raise RuntimeError("Production requires ENCRYPTION_KEY and HTTPS PUBLIC_ORIGIN")


settings = Settings()
settings.validate_production()
