import httpx

from app.ai.base import AIProvider, AIProviderError


class OpenAICompatibleProvider(AIProvider):
    """Any OpenAI-compatible /chat/completions endpoint (base URL + API key)."""

    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url or not api_key or not model:
            raise AIProviderError("OpenAI-compatible base_url, api_key and model are required")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=60)

    def complete(self, system: str, prompt: str) -> str:
        try:
            resp = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={"authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise AIProviderError(
                f"OpenAI-compatible request failed: {type(exc).__name__}"
            ) from None
