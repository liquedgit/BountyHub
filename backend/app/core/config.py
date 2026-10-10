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


@lru_cache
def get_settings() -> Settings:
    return Settings()
