from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "BountyHub"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg2://bountyhub:bountyhub@localhost:5432/bountyhub"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    auth_cookie_name: str = "access_token"
    auth_cookie_secure: bool = False
    login_max_failures: int = 5
    login_window_seconds: int = 15 * 60
    login_global_max_failures: int = 50

    subfinder_bin: str = "subfinder"
    httpx_bin: str = "pd-httpx"
    recon_tool_timeout: int = 300


def check_secrets(settings: Settings) -> None:
    """Refuse a weak JWT secret outside development. Never echoes the secret."""
    if settings.app_env == "development":
        return
    secret = settings.jwt_secret
    if len(secret) < 32 or secret.startswith("change-me"):
        raise RuntimeError(
            "JWT_SECRET must be at least 32 characters and not a 'change-me' "
            f"placeholder when APP_ENV is '{settings.app_env}'"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
