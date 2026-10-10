from app.ai.base import AIProvider, AIProviderError
from app.ai.claude import ClaudeProvider
from app.ai.openai_compat import OpenAICompatibleProvider
from app.repositories.settings import SettingsRepository

PROVIDER_CLAUDE = "claude"
PROVIDER_OPENAI = "openai_compatible"
PROVIDERS = (PROVIDER_CLAUDE, PROVIDER_OPENAI)

KEY_PROVIDER = "ai.provider"
KEY_CLAUDE_TOKEN = "ai.claude.token"
KEY_CLAUDE_MODEL = "ai.claude.model"
KEY_OPENAI_BASE_URL = "ai.openai.base_url"
KEY_OPENAI_API_KEY = "ai.openai.api_key"
KEY_OPENAI_MODEL = "ai.openai.model"

SECRET_KEYS = frozenset({KEY_CLAUDE_TOKEN, KEY_OPENAI_API_KEY})


class AIProviderFactory:
    """Builds the configured AIProvider from the local settings table."""

    def __init__(self, settings: SettingsRepository) -> None:
        self._settings = settings

    def create(self) -> AIProvider:
        choice = self._settings.get(KEY_PROVIDER)
        if choice == PROVIDER_CLAUDE:
            return ClaudeProvider(
                token=self._settings.get(KEY_CLAUDE_TOKEN) or "",
                model=self._settings.get(KEY_CLAUDE_MODEL) or "",
            )
        if choice == PROVIDER_OPENAI:
            return OpenAICompatibleProvider(
                base_url=self._settings.get(KEY_OPENAI_BASE_URL) or "",
                api_key=self._settings.get(KEY_OPENAI_API_KEY) or "",
                model=self._settings.get(KEY_OPENAI_MODEL) or "",
            )
        raise AIProviderError("No AI provider selected")
