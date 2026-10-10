import httpx

from app.ai.base import AIProvider, AIProviderError

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-5-5"


class ClaudeProvider(AIProvider):
    """Claude via the OAuth session token produced by `claude setup-token`."""

    name = "claude"

    def __init__(
        self,
        token: str,
        model: str = DEFAULT_CLAUDE_MODEL,
        client: httpx.Client | None = None,
        max_tokens: int = 4096,
    ) -> None:
        if not token:
            raise AIProviderError("Claude setup-token is not configured")
        self._token = token
        self._model = model or DEFAULT_CLAUDE_MODEL
        self._client = client or httpx.Client(timeout=60)
        self._max_tokens = max_tokens

    def complete(self, system: str, prompt: str) -> str:
        try:
            resp = self._client.post(
                ANTHROPIC_URL,
                headers={
                    "authorization": f"Bearer {self._token}",
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "oauth-2025-04-20",
                },
                json={
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            blocks = resp.json()["content"]
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            # Never include request headers/credentials in the message.
            raise AIProviderError(f"Claude request failed: {type(exc).__name__}") from None
