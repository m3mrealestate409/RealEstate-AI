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
    # Don't expose the interactive schema / full endpoint enumeration in
    # production. (Live it's already unreachable — Caddy doesn't proxy /docs —
    # but this removes the surface entirely, including a base-compose run.)
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# CORS. Every request authenticates with an *explicit* header — the admin app
# sends `Authorization: Bearer <jwt>`, the embeddable widget sends `X-API-Key` —
# and never with cookies. With no ambient (cookie) credentials, an origin
# allow-list buys almost no security: a third-party page still cannot read a
# user's token or a tenant's API key. It does, however, break the widget, which
# is meant to be embedded on *arbitrary* customer websites whose origins we
# cannot know in advance — a strict allow-list makes every such embed fail its
# CORS preflight ("Failed to fetch"). So we allow any origin with credentialed
# mode off ("*" + credentials is invalid anyway). The admin app is same-origin
# with the API behind the web edge, so this only affects cross-origin widget
# calls, which are gated by the per-tenant API key, not by origin.
_cors_origins = ["*"]
_allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers on every response. Deliberately NOT a strict script/style CSP:
# this app also serves /docs (Swagger) and the printable receipt HTML, which use
# inline styles — a `default-src` policy would break them. We add the headers
# that are safe everywhere, and use CSP only for clickjacking (`frame-ancestors`),
# which restricts framing without touching scripts/styles. The widget is embedded
# via <script>, not an iframe of our origin, so framing controls don't affect it.
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
    )
    if settings.is_production:  # only meaningful over TLS
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
    return response

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
