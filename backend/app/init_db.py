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
    logger.info("Database initialised.")


if __name__ == "__main__":
    init_db()
