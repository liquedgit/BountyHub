from typing import Literal

from pydantic import BaseModel, Field


class AISettingsUpdate(BaseModel):
    """Partial update; omitted fields are left unchanged."""

    provider: Literal["claude", "openai_compatible"] | None = None
    claude_token: str | None = Field(default=None, min_length=1)
    claude_model: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = Field(default=None, min_length=1)
    openai_model: str | None = None


class AISettingsResponse(BaseModel):
    """Credentials are never returned, only whether they are set."""

    provider: str | None
    claude_token_set: bool
    claude_model: str | None
    openai_base_url: str | None
    openai_api_key_set: bool
    openai_model: str | None
