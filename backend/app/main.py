"""
FastAPI application entrypoint.

API-first (Constitution §13): every capability here is an HTTP endpoint that
the web app and all future clients (CRM, WhatsApp, mobile) consume identically.
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.v1 import (
    admin,
    analytics,
    apikeys,
    auth,
    billing,
    calculate,
    extract,
    knowledge,
    leads,
    livechat,
    manage,
    notify,
    projects,
    query,
    settings as settings_router,
    superadmin,
    system,
    users,
    widget_api,
)
from app.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Chaahat Homes — AI Knowledge Engine",
    description="Hybrid real-estate knowledge engine (SQL + Calc + RAG + LLM).",
    version=__version__,
)

# CORS — allow all origins only in debug/dev; in production use an explicit
# allow-list from CORS_ORIGINS (comma-separated). Wildcard origins are never
# combined with credentials in production.
if settings.app_debug:
    _cors_origins = ["*"]
    _allow_credentials = False  # "*" + credentials is invalid / unsafe
else:
    _cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(query.router)
app.include_router(projects.router)
app.include_router(calculate.router)
app.include_router(admin.router)
app.include_router(analytics.router)
app.include_router(settings_router.router)
app.include_router(manage.router)
app.include_router(users.router)
app.include_router(knowledge.router)
app.include_router(system.router)
app.include_router(superadmin.router)
app.include_router(extract.router)
app.include_router(apikeys.router)
app.include_router(widget_api.router)
app.include_router(leads.router)
app.include_router(livechat.router)
app.include_router(notify.router)
app.include_router(billing.router)

# Static assets (the embeddable chat widget served at /static/widget.js).
_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(_static_dir, exist_ok=True)


# Serve the widget with no-cache so embedding sites always fetch the latest
# version (avoids stale cached copies after an update — no ?v= bump needed).
@app.get("/static/widget.js", include_in_schema=False)
def _widget_js():
    from fastapi.responses import FileResponse

    return FileResponse(
        os.path.join(_static_dir, "widget.js"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.on_event("startup")
def _chat_retention_purge():
    """Apply the live-chat retention policy once at boot (cheap, best-effort)."""
    try:
        from app.database import SessionLocal
        from app.services.livechat import purge_old

        db = SessionLocal()
        try:
            purge_old(db)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — never block startup on cleanup
        pass


@app.get("/health", tags=["system"])
def health():
    from app.services.runtime_config import public_llm_config

    cfg = public_llm_config()
    return {
        "status": "ok",
        "version": __version__,
        "llm_provider": cfg["provider"],
        "embedding_provider": cfg["embedding_provider"],
        "key_set": cfg["key_set"],
    }
