"""Gemini embeddings (gemini-embedding-001, 768-dim). SDK imported lazily."""
import logging
import re
import time

from app.config import settings
from app.services.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

# Errors worth retrying: rate limits / quota / transient server issues.
_RETRYABLE = ("quota", "rate", "exhaust", "429", "deadline", "unavailable", "503", "500", "retry_delay", "seconds:")


def _retry_after_seconds(exc: Exception) -> int | None:
    """Gemini returns a suggested `retry_delay { seconds: N }` on rate limits."""
    m = re.search(r"seconds:\s*(\d+)", str(exc))
    return int(m.group(1)) + 1 if m else None


class GeminiEmbeddingProvider(EmbeddingProvider):
    name = "gemini"

    # Gemini's embed_content accepts a LIST of texts and returns one vector each
    # in a single call. Batching turns "one API round-trip per chunk" (minutes
    # for a big brochure) into a handful of calls (seconds), and — just as
    # importantly — keeps us well under the API's per-minute rate limit.
    BATCH = 100
    ATTEMPTS = 5

    def __init__(self, api_key: str | None = None, model: str | None = None, dim: int = 768) -> None:
        key = api_key or (settings.gemini_api_key if settings.gemini_ready else "")
        if not key or key == "PASTE_YOUR_KEY_HERE":
            raise RuntimeError("Gemini API key not set for embeddings.")
        import google.generativeai as genai

        genai.configure(api_key=key)
        self._genai = genai
        self.dim = dim
        self._model = model or settings.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.BATCH):
            out.extend(self._embed_group(texts[i : i + self.BATCH]))
        return out

    def _embed_group(self, group: list[str]) -> list[list[float]]:
        last: Exception | None = None
        for attempt in range(self.ATTEMPTS):
            try:
                # output_dimensionality keeps vectors at 768 to fit the VECTOR(768)
                # column (gemini-embedding-001 is 3072 by default). Cosine distance
                # is scale-invariant, so no re-normalisation is needed.
                res = self._genai.embed_content(
                    model=f"models/{self._model}", content=group, output_dimensionality=self.dim
                )
                emb = res["embedding"]
                # A list input returns a list of vectors; be defensive in case a
                # single vector comes back (e.g. a one-item group on some SDKs).
                if emb and isinstance(emb[0], (int, float)):
                    return [list(emb)]
                return [list(v) for v in emb]
            except Exception as exc:  # noqa: BLE001
                last = exc
                retryable = any(k in str(exc).lower() for k in _RETRYABLE)
                if attempt == self.ATTEMPTS - 1 or not retryable:
                    break
                delay = min(_retry_after_seconds(exc) or (5 * (2 ** attempt)), 60)
                logger.warning("Embedding rate-limited; retrying in %ss (attempt %s/%s).",
                               delay, attempt + 1, self.ATTEMPTS)
                time.sleep(delay)
        raise last
