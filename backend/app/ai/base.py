from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """Raised when a provider is misconfigured or its upstream call fails."""


class AIProvider(ABC):
    """A text-completion backend used by AITriageService."""

    name: str

    @abstractmethod
    def complete(self, system: str, prompt: str) -> str:
        """Return the model's text reply for the given system + user prompt."""
