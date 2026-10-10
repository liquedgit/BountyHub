from app.ai import factory as keys
from app.repositories.settings import SettingsRepository
from app.schemas.settings import AISettingsResponse, AISettingsUpdate

_FIELD_TO_KEY = {
    "provider": keys.KEY_PROVIDER,
    "claude_token": keys.KEY_CLAUDE_TOKEN,
    "claude_model": keys.KEY_CLAUDE_MODEL,
    "openai_base_url": keys.KEY_OPENAI_BASE_URL,
    "openai_api_key": keys.KEY_OPENAI_API_KEY,
    "openai_model": keys.KEY_OPENAI_MODEL,
}


class SettingsService:
    def __init__(self, repo: SettingsRepository) -> None:
        self._repo = repo

    def get_ai_settings(self) -> AISettingsResponse:
        g = self._repo.get
        return AISettingsResponse(
            provider=g(keys.KEY_PROVIDER),
            claude_token_set=bool(g(keys.KEY_CLAUDE_TOKEN)),
            claude_model=g(keys.KEY_CLAUDE_MODEL),
            openai_base_url=g(keys.KEY_OPENAI_BASE_URL),
            openai_api_key_set=bool(g(keys.KEY_OPENAI_API_KEY)),
            openai_model=g(keys.KEY_OPENAI_MODEL),
        )

    def update_ai_settings(self, update: AISettingsUpdate) -> AISettingsResponse:
        for field, value in update.model_dump(exclude_none=True).items():
            self._repo.set(_FIELD_TO_KEY[field], value)
        return self.get_ai_settings()
