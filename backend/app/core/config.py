"""Application settings, loaded from backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that must never reach a running instance — they are documentation, not secrets.
PLACEHOLDER_SECRETS = {"change-me", "your-secret-key", "secret", "changeme"}
MIN_SECRET_LENGTH = 32

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api"

    database_url: str
    # Log every SQL statement. Off by default — very noisy.
    sql_echo: bool = False

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    apple_client_id: str = ""
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""
    apple_redirect_uri: str = "http://localhost:8000/auth/apple/callback"

    frontend_url: str = "http://localhost:5173"
    # Comma-separated in .env; pydantic-settings would try to JSON-decode a list field.
    cors_origins: str = "http://localhost:5173"

    # Uploads. Paths are resolved relative to the backend directory.
    upload_dir: str = "uploads"
    max_image_bytes: int = 10 * 1024 * 1024
    max_document_bytes: int = 25 * 1024 * 1024

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from_name: str = "Deal Network"
    smtp_starttls: bool = True
    email_enabled: bool = True

    @field_validator("jwt_secret_key")
    @classmethod
    def _check_secret(cls, value: str) -> str:
        """Refuse to boot on a placeholder or a weak secret.

        Anyone who knows the secret can mint a token for any account, so a
        copied-and-not-edited .env is an authentication bypass, not a nit.
        """
        if value.strip().lower() in PLACEHOLDER_SECRETS:
            raise ValueError(
                "JWT_SECRET_KEY is still the example placeholder. Generate one with:\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if len(value) < MIN_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MIN_SECRET_LENGTH} characters "
                f"(got {len(value)}). Generate one with:\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return value

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        return path if path.is_absolute() else BASE_DIR / path

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def apple_enabled(self) -> bool:
        return bool(
            self.apple_client_id
            and self.apple_team_id
            and self.apple_key_id
            and self.apple_private_key
        )

    @property
    def email_configured(self) -> bool:
        return bool(self.email_enabled and self.smtp_user and self.smtp_pass)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
