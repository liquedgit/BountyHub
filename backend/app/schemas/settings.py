from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, TypeAdapter, field_validator


class AISettingsUpdate(BaseModel):
    """Partial update; omitted fields are left unchanged."""

    provider: Literal["claude", "openai_compatible"] | None = None
    claude_token: str | None = Field(default=None, min_length=1)
    claude_model: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = Field(default=None, min_length=1)
    openai_model: str | None = None

    @field_validator("openai_base_url")
    @classmethod
    def _http_url(cls, v: str | None) -> str | None:
        if v is not None:
            TypeAdapter(AnyHttpUrl).validate_python(v)
        return v


class AISettingsResponse(BaseModel):
    """Credentials are never returned, only whether they are set."""

    provider: str | None
    claude_token_set: bool
    claude_model: str | None
    openai_base_url: str | None
    openai_api_key_set: bool
    openai_model: str | None
