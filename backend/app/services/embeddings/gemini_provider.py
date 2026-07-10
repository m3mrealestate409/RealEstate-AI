"""Gemini embeddings (text-embedding-004, 768-dim). SDK imported lazily."""
from app.config import settings
from app.services.embeddings.base import EmbeddingProvider


class GeminiEmbeddingProvider(EmbeddingProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, dim: int = 768) -> None:
        key = api_key or (settings.gemini_api_key if settings.gemini_ready else "")
        if not key or key == "PASTE_YOUR_KEY_HERE":
            raise RuntimeError("Gemini API key not set for embeddings.")
        import google.generativeai as genai

        genai.configure(api_key=key)
        self._genai = genai
        self.dim = dim
        self._model = settings.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            res = self._genai.embed_content(
                model=f"models/{self._model}", content=t
            )
            out.append(res["embedding"])
        return out
