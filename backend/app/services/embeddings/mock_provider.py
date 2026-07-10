"""
Deterministic local embedding — no API key needed.

Uses a hashing bag-of-words projected into `dim` dimensions and L2-normalised.
It is NOT semantically strong, but it is stable and lets the full RAG pipeline
(ingest -> store in pgvector -> cosine search) run and be tested offline.
Swap EMBEDDING_PROVIDER=gemini for real semantic embeddings.
"""
import hashlib
import math
import re

from app.services.embeddings.base import EmbeddingProvider

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class MockEmbeddingProvider(EmbeddingProvider):
    name = "mock"

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN_RE.findall(text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]
