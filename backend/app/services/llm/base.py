"""
LLM provider interface.

The application NEVER imports a vendor SDK directly (Constitution §12).
It depends only on this interface; the concrete provider is chosen by config.
Swapping Gemini -> Claude -> Ollama is a config change, not a code change.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str  # 'system' | 'user' | 'assistant'
    content: str


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    raw: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """Vendor-agnostic completion interface."""

    name: str = "base"

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        temperature: float = 0.2,
        max_tokens: int = 1024,
        response_json: bool = False,
    ) -> LLMResponse:
        """Return a completion. Implementations must never raise on missing
        keys at import time — only when actually called without config."""
        raise NotImplementedError
