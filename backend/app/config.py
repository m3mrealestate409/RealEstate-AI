"""
Central configuration. All settings come from environment variables (.env).

Constitution ties:
  §12 LLM Independence  -> LLM_PROVIDER / EMBEDDING_PROVIDER are config, not code.
  §19 Security          -> secrets read from env only, never hardcoded in logic.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_env: str = "development"
    app_debug: bool = True
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"
    # Comma-separated allowed browser origins in production (CORS). Ignored in
    # debug mode (which allows all origins for local dev).
    cors_origins: str = ""

    # --- Database ---
    database_url: str = (
        "postgresql+psycopg://chaahat:chaahat_pass@localhost:5432/chaahat_engine"
    )

    # --- Redis (session memory) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM provider layer ---
    llm_provider: str = "mock"          # mock | gemini | claude | openai | openrouter | ollama
    # flash-lite has "thinking" OFF by default → much faster + cheaper, and this
    # engine's LLM work is simple/grounded so it doesn't need extended reasoning.
    llm_model: str = "gemini-flash-lite-latest"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    claude_api_key: str = ""
    openrouter_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # --- Embeddings ---
    embedding_provider: str = "mock"    # mock | gemini
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768

    # --- RAG ---
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.35

    # --- Seed admin (org-admin of the default org) ---
    seed_admin_email: str = "admin@chaahat.local"
    seed_admin_password: str = "admin123"

    # --- Seed super-admin (the SaaS owner; no org, manages all tenants) ---
    seed_super_admin_email: str = "owner@engine.local"
    seed_super_admin_password: str = "owner123"

    @property
    def gemini_ready(self) -> bool:
        """True only when a real Gemini key has been supplied."""
        return bool(self.gemini_api_key) and self.gemini_api_key != "PASTE_YOUR_KEY_HERE"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() not in ("development", "dev", "test", "testing", "local")


_WEAK_SECRETS = {"", "dev-secret-change-me", "change-this-to-a-long-random-string-in-production"}


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # C1 — never boot production with a weak/default JWT secret. Anyone who knows
    # the default string could forge a super-admin token. Fail fast instead.
    if s.is_production and (s.secret_key in _WEAK_SECRETS or len(s.secret_key) < 32):
        raise RuntimeError(
            "SECRET_KEY must be a strong, unique 32+ character random value in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return s


settings = get_settings()
