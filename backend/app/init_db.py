"""
Database bootstrap: enable extensions, create tables, add trigram index.

For V1 we create schema directly from the ORM metadata (fast to iterate).
Alembic migrations can be layered on later without changing the models.
"""
import logging

from sqlalchemy import text

from app.database import Base, engine
from app import models  # noqa: F401  (ensure models are registered on Base)

logger = logging.getLogger(__name__)


def init_db() -> None:
    with engine.begin() as conn:
        # pgvector for embeddings, pg_trgm for fuzzy project-name matching.
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_projects_name_trgm "
                "ON projects USING gin (name gin_trgm_ops)"
            )
        )
        # Lightweight column additions (create_all won't ALTER existing tables).
        conn.execute(
            text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'")
        )
        conn.execute(
            text("UPDATE documents SET status='completed' WHERE indexed_at IS NOT NULL AND status IS NULL")
        )
        # Multi-tenancy columns on pre-existing tables.
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id BIGINT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN DEFAULT false"))
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS organization_id BIGINT"))
        conn.execute(text("ALTER TABLE query_log ADD COLUMN IF NOT EXISTS organization_id BIGINT"))
        # Employee tiers + per-tier daily limits.
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'basic'"))
        conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS basic_daily_limit INTEGER DEFAULT 25"))
        conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS advanced_daily_limit INTEGER DEFAULT 100"))
        # Richer project attributes.
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_type TEXT"))
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS land_parcel TEXT"))
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS green_area TEXT"))
        conn.execute(text("ALTER TABLE builders ADD COLUMN IF NOT EXISTS organization_id BIGINT"))
        # Per-payment-plan pricing: a Price may target a specific payment plan
        # (NULL = the base price for all plans).
        conn.execute(text("ALTER TABLE prices ADD COLUMN IF NOT EXISTS payment_plan_id BIGINT"))
        # Rise type + launch price (shown on the project page).
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS rise_type TEXT"))
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS launch_price NUMERIC"))
        # Editable chat-widget greeting + org-wide assistant persona.
        conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS widget_greeting TEXT"))
        conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS assistant_persona TEXT"))
        # CRM webhook — captured leads are POSTed here.
        conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS crm_webhook_url TEXT"))
        # Chat widget identity — assistant display name + avatar image path.
        conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS assistant_name TEXT"))
        conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS assistant_avatar TEXT"))
        # Per-employee Live Chat (takeover) access.
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_live_chat BOOLEAN DEFAULT false"))
        # New-chat notification provider + config (Telegram / webhook / etc.).
        conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS notify_provider TEXT DEFAULT 'off'"))
        conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS notify_config JSONB"))
        # Live-chat presence heartbeat.
        conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT now()"))
        # Query source (app = staff, widget = website visitor) for demand analytics.
        conn.execute(text("ALTER TABLE query_log ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'app'"))
        # What each API key is plugged into: website (public widget) | internal (CRM…).
        conn.execute(text("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS channel TEXT DEFAULT 'website'"))
    logger.info("Database initialised.")


if __name__ == "__main__":
    init_db()
