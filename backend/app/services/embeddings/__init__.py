"""Embedding provider abstraction (mirrors the LLM layer)."""
from app.services.embeddings.factory import get_embedding_provider

__all__ = ["get_embedding_provider"]
