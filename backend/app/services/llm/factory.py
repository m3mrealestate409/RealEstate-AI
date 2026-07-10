"""
Provider factory. Reads the effective LLM config (env + admin settings) and
returns the right implementation. Falls back to mock if a provider is
misconfigured, so deterministic paths keep working (graceful degradation).

The provider is cached by config signature and rebuilt when an admin changes
settings (reset_llm_provider()).
"""
import logging

from app.services.llm.base import LLMProvider
from app.services.llm.mock_provider import MockLLMProvider

logger = logging.getLogger(__name__)

_cache: dict[tuple, LLMProvider] = {}


def _build(provider: str, model: str, api_key: str) -> LLMProvider:
    provider = (provider or "mock").lower()

    if provider == "mock":
        return MockLLMProvider()

    if provider == "gemini":
        try:
            from app.services.llm.gemini_provider import GeminiLLMProvider

            return GeminiLLMProvider(api_key=api_key, model=model)
        except Exception as exc:
            logger.warning("Gemini provider unavailable (%s); using mock.", exc)
            return MockLLMProvider()

    # Future providers (claude, openai, openrouter, ollama) plug in here.
    logger.warning("LLM_PROVIDER='%s' not implemented yet; using mock.", provider)
    return MockLLMProvider()


def get_llm_provider() -> LLMProvider:
    from app.services.runtime_config import get_llm_config

    cfg = get_llm_config()
    key = cfg.get("api_key") or ""
    sig = (cfg["provider"], cfg["model"], key[:8])
    if sig not in _cache:
        _cache.clear()
        _cache[sig] = _build(cfg["provider"], cfg["model"], key)
    return _cache[sig]


def reset_llm_provider() -> None:
    _cache.clear()
