"""
AI Settings (admin only). Lets an admin choose the LLM/embedding provider and
paste an API key from the UI. The key is stored server-side and never returned
to the browser (Constitution §19). Includes a live "test connection" check.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.audit import record_audit
from app.core.security import require_role
from app.database import get_db
from app.models import User
from app.services.llm.base import Message
from app.services.runtime_config import public_llm_config, set_llm_config

router = APIRouter(prefix="/v1/admin/settings", tags=["settings"])

SUPPORTED_PROVIDERS = ["mock", "gemini"]  # extend as providers are implemented


class LLMSettingsIn(BaseModel):
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None            # write-only; never returned
    embedding_provider: str | None = None
    embedding_model: str | None = None


@router.get("/llm")
def get_llm_settings(admin: User = Depends(require_role("admin"))):
    return {
        "supported_providers": SUPPORTED_PROVIDERS,
        "current": public_llm_config(),
    }


@router.put("/llm")
def update_llm_settings(
    payload: LLMSettingsIn,
    admin: User = Depends(require_role("admin")),
    db=Depends(get_db),
):
    updated = set_llm_config(payload.model_dump())
    # Audit the change WITHOUT logging the secret key.
    safe = {k: v for k, v in payload.model_dump().items() if k != "api_key"}
    safe["api_key_changed"] = bool(payload.api_key)
    record_audit(db, user_id=admin.id, action="UPDATE", entity="settings",
                 entity_id=None, after=safe)
    db.commit()
    return updated


STATIC_LLM_MODELS = ["gemini-flash-latest", "gemini-2.0-flash", "gemini-pro-latest"]
STATIC_EMBED_MODELS = ["gemini-embedding-001"]


@router.get("/models")
def list_models(admin: User = Depends(require_role("admin"))):
    """Available model names. Queried live from Gemini when a key is set,
    else a curated fallback list."""
    from app.services.runtime_config import get_llm_config

    cfg = get_llm_config()
    key = cfg.get("api_key") or ""
    if not key or key == "PASTE_YOUR_KEY_HERE":
        return {"llm_models": STATIC_LLM_MODELS, "embedding_models": STATIC_EMBED_MODELS, "source": "static"}
    try:
        import google.generativeai as genai

        genai.configure(api_key=key)
        llm, emb = [], []
        for m in genai.list_models():
            name = m.name.replace("models/", "")
            methods = m.supported_generation_methods
            if "generateContent" in methods and "gemini" in name and "preview" not in name:
                llm.append(name)
            if "embedContent" in methods:
                emb.append(name)
        return {
            "llm_models": llm or STATIC_LLM_MODELS,
            "embedding_models": emb or STATIC_EMBED_MODELS,
            "source": "live",
        }
    except Exception as exc:
        return {"llm_models": STATIC_LLM_MODELS, "embedding_models": STATIC_EMBED_MODELS,
                "source": "static", "error": str(exc)[:120]}


@router.post("/llm/test")
def test_llm(admin: User = Depends(require_role("admin"))):
    """Runs a tiny live completion with the CURRENT saved config."""
    from app.services.llm import get_llm_provider

    provider = get_llm_provider()
    try:
        resp = provider.complete(
            system="You are a connection test. Reply with the single word: OK.",
            messages=[Message(role="user", content="CONTEXT: ping\nReply OK.")],
            max_tokens=256,
        )
        return {
            "ok": True,
            "provider": resp.provider,
            "model": resp.model,
            "sample": (resp.text or "")[:120],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
