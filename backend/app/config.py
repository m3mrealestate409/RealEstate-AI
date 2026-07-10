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

    # --- Database ---
    database_url: str = (
        "postgresql+psycopg://chaahat:chaahat_pass@localhost:5432/chaahat_engine"
    )

    # --- Redis (session memory) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM provider layer ---
    llm_provider: str = "mock"          # mock | gemini | claude | openai | openrouter | ollama
    llm_model: str = "gemini-flash-latest"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    claude_api_key: str = ""
    openrouter_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # --- Embeddings ---
    embedding_provider: str = "mock"    # mock | gemini
    embedding_model: str = "text-embedding-004"
    embedding_dim: int = 768

    # --- RAG ---
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.35

    # --- Seed admin ---
    seed_admin_email: str = "admin@chaahat.local"
    seed_admin_password: str = "admin123"

    @property
    def gemini_ready(self) -> bool:
        """True only when a real Gemini key has been supplied."""
        return bool(self.gemini_api_key) and self.gemini_api_key != "PASTE_YOUR_KEY_HERE"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
