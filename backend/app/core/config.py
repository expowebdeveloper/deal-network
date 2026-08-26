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
    # Per-type ceilings for a single upload, overridable in .env. These are what
    # this deployment will carry; the plan's `files.max_file_size_bytes` is a
    # separate ceiling and the smaller of the two always wins (services/files.py).
    max_image_bytes: int = 10 * 1024 * 1024       # MAX_IMAGE_BYTES
    max_video_bytes: int = 30 * 1024 * 1024       # MAX_VIDEO_BYTES
    max_document_bytes: int = 25 * 1024 * 1024    # MAX_DOCUMENT_BYTES

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from_name: str = "Deal Network"
    smtp_starttls: bool = True
    email_enabled: bool = True

    # --- Stripe ----------------------------------------------------------
    # All optional: with no secret key the billing endpoints answer 503
    # BILLING_NOT_CONFIGURED and the rest of the app runs untouched, so the
    # stack still boots on a machine that has no Stripe account yet.
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    # Recurring Price ids (price_…, not product ids) from the Stripe dashboard.
    stripe_price_member: str = ""
    stripe_price_professional: str = ""
    # Point the SDK somewhere other than api.stripe.com. Only for `stripe-mock`,
    # Stripe's own fake API, which makes the billing path testable in CI without
    # an account. Must stay empty in production — it is the difference between
    # talking to Stripe and talking to something claiming to be Stripe.
    stripe_api_base: str = ""

    # Where Stripe sends the browser back to. Appended to frontend_url.
    stripe_success_path: str = "/billing/success"
    stripe_cancel_path: str = "/plans"
    stripe_portal_return_path: str = "/plans"
    # How long a pre-signup plan choice stays spendable (backend_flow.md 7.1).
    signup_intent_ttl_minutes: int = 60

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

    @property
    def stripe_enabled(self) -> bool:
        """Whether the billing endpoints can talk to Stripe at all."""
        return bool(self.stripe_secret_key)

    @property
    def stripe_webhook_ready(self) -> bool:
        """Whether an inbound webhook can have its signature verified.

        Without the signing secret the webhook endpoint refuses every delivery
        rather than trusting an unauthenticated POST that grants paid plans.
        """
        return bool(self.stripe_secret_key and self.stripe_webhook_secret)

    @property
    def stripe_live_mode(self) -> bool:
        return self.stripe_secret_key.startswith("sk_live_")

    def stripe_price_for(self, plan: str) -> str:
        """The configured Price id for a paid tier, or "" when unset."""
        return {
            "member": self.stripe_price_member,
            "professional": self.stripe_price_professional,
        }.get(plan, "")

    @property
    def stripe_plan_by_price(self) -> dict[str, str]:
        """Price id -> plan tier, for reading a Stripe subscription back."""
        return {
            price: plan
            for plan, price in (
                ("member", self.stripe_price_member),
                ("professional", self.stripe_price_professional),
            )
            if price
        }

    def frontend_link(self, path: str) -> str:
        return f"{self.frontend_url.rstrip('/')}/{path.lstrip('/')}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
