"""
FastAPI application entrypoint.

API-first (Constitution §13): every capability here is an HTTP endpoint that
the web app and all future clients (CRM, WhatsApp, mobile) consume identically.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import (
    admin,
    analytics,
    auth,
    calculate,
    knowledge,
    manage,
    projects,
    query,
    settings as settings_router,
    superadmin,
    system,
    users,
)
from app.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Chaahat Homes — AI Knowledge Engine",
    description="Hybrid real-estate knowledge engine (SQL + Calc + RAG + LLM).",
    version=__version__,
)

# CORS — tighten origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else [],
    allow_credentials=True,
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
