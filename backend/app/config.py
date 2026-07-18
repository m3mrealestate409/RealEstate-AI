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
    # Defaults are FAIL-CLOSED: an environment that forgets to set APP_ENV /
    # APP_DEBUG is treated as production (strict CORS, secret guard on). Local
    # dev and CI opt OUT explicitly (.env sets APP_ENV=development, APP_DEBUG=true;
    # tests set APP_ENV=testing). See get_settings() below.
    app_env: str = "production"
    app_debug: bool = False
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


# Substrings that mark a secret as derived from a placeholder rather than random.
# The old exact-match denylist missed values like
# "dev-secret-change-me-please-0123456789abcdef" (43 chars) — long enough and not
# an exact match, so it passed. Substring + character-variety checks close that.
_WEAK_MARKERS = (
    "dev-secret", "change-me", "changeme", "change-this", "your-secret",
    "your_secret", "secret-key", "placeholder", "please", "example",
)


def _is_weak_secret(key: str) -> bool:
    """True if this SECRET_KEY is unfit for production: too short, derived from a
    known placeholder, or too low-variety to be a real random value."""
    if len(key) < 32:
        return True
    low = key.lower()
    if any(marker in low for marker in _WEAK_MARKERS):
        return True
    if len(set(key)) < 12:  # e.g. "aaaa…", repeated/patterned strings
        return True
    return False


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # C1 — never boot production with a weak/default JWT secret. Anyone who knows
    # (or can derive) the value could forge a super-admin token. Fail fast.
    if s.is_production and _is_weak_secret(s.secret_key):
        raise RuntimeError(
            "SECRET_KEY must be a strong, unique 32+ character random value in production "
            "(no placeholder text like 'dev-secret'/'change-me', high character variety). "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return s


settings = get_settings()
