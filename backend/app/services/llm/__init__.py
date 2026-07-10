"""LLM provider abstraction (Constitution §12 — swap provider by config only)."""
from app.services.llm.factory import get_llm_provider

__all__ = ["get_llm_provider"]
