"""
Runtime configuration for the LLM/embedding layer.

Admins can change the active provider and paste an API key from the UI. The
value is stored server-side in the `settings` table and merged OVER the .env
defaults. The key is NEVER returned to the browser (only a masked status),
satisfying the Security Policy (§19 — no keys in frontend).
"""
from __future__ import annotations

from sqlalchemy.orm.attributes import flag_modified

from app.config import settings as env
from app.database import SessionLocal
from app.models import Setting

_LLM_KEY = "llm_config"


def _defaults() -> dict:
    return {
        "provider": env.llm_provider,
        "model": env.llm_model,
        "api_key": env.gemini_api_key if env.gemini_ready else "",
        "embedding_provider": env.embedding_provider,
    }


def get_llm_config() -> dict:
    """Effective config = env defaults overlaid with stored admin settings."""
    cfg = _defaults()
    db = SessionLocal()
    try:
        row = db.get(Setting, _LLM_KEY)
        if row and row.value:
            for k, v in row.value.items():
                if v is not None and v != "":
                    cfg[k] = v
    finally:
        db.close()
    return cfg


def public_llm_config() -> dict:
    """Browser-safe view: provider/model + whether a key is set (masked)."""
    cfg = get_llm_config()
    key = cfg.get("api_key") or ""
    return {
        "provider": cfg["provider"],
        "model": cfg["model"],
        "embedding_provider": cfg.get("embedding_provider", "mock"),
        "key_set": bool(key) and key != "PASTE_YOUR_KEY_HERE",
        "key_masked": (key[:4] + "…" + key[-4:]) if len(key) > 8 else "",
    }


def set_llm_config(new: dict) -> dict:
    """Persist provided fields (None/empty ignored). Resets the provider cache."""
    db = SessionLocal()
    try:
        row = db.get(Setting, _LLM_KEY)
        data = dict(row.value) if row and row.value else {}
        for k in ("provider", "model", "api_key", "embedding_provider"):
            if k in new and new[k] is not None and new[k] != "":
                data[k] = new[k]
        if row:
            row.value = data
            flag_modified(row, "value")
        else:
            db.add(Setting(key=_LLM_KEY, value=data))
        db.commit()
    finally:
        db.close()

    # Rebuild providers with the new config on next use (lazy import avoids cycle).
    from app.services.embeddings.factory import reset_embedding_provider
    from app.services.llm.factory import reset_llm_provider

    reset_llm_provider()
    reset_embedding_provider()
    return public_llm_config()
