"""Embedding provider factory (runtime-config-driven, mock fallback)."""
import logging

from app.config import settings
from app.services.embeddings.base import EmbeddingProvider
from app.services.embeddings.mock_provider import MockEmbeddingProvider

logger = logging.getLogger(__name__)

_cache: dict[tuple, EmbeddingProvider] = {}


def get_embedding_provider() -> EmbeddingProvider:
    from app.services.runtime_config import get_llm_config

    cfg = get_llm_config()
    provider = (cfg.get("embedding_provider") or "mock").lower()
    key = cfg.get("api_key") or ""
    dim = settings.embedding_dim
    sig = (provider, key[:8], dim)

    if sig in _cache:
        return _cache[sig]

    _cache.clear()
    built: EmbeddingProvider
    if provider == "gemini":
        try:
            from app.services.embeddings.gemini_provider import GeminiEmbeddingProvider

            built = GeminiEmbeddingProvider(api_key=key, dim=dim)
        except Exception as exc:
            logger.warning("Gemini embeddings unavailable (%s); using mock.", exc)
            built = MockEmbeddingProvider(dim=dim)
    else:
        built = MockEmbeddingProvider(dim=dim)

    _cache[sig] = built
    return built


def reset_embedding_provider() -> None:
    _cache.clear()
