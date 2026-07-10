"""Gemini embeddings (text-embedding-004, 768-dim). SDK imported lazily."""
from app.config import settings
from app.services.embeddings.base import EmbeddingProvider


class GeminiEmbeddingProvider(EmbeddingProvider):
    name = "gemini"

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
        for t in texts:
            # output_dimensionality keeps vectors at 768 to fit the VECTOR(768)
            # column (gemini-embedding-001 is 3072 by default). Cosine distance
            # is scale-invariant, so no re-normalisation is needed.
            res = self._genai.embed_content(
                model=f"models/{self._model}", content=t, output_dimensionality=self.dim
            )
            out.append(res["embedding"])
        return out
