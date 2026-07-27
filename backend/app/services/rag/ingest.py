"""
RAG ingestion: PDF -> per-page text -> chunks -> embeddings -> pgvector.

Page numbers are preserved on every chunk to satisfy the Citation Policy
(§9). Re-indexing a new document version deactivates old chunks so stale
brochure text is never retrieved.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Document, RagChunk
from app.services.embeddings import get_embedding_provider

CHUNK_CHARS = 1200
CHUNK_OVERLAP = 150


def _chunk_text(text: str) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_CHARS
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
    return chunks


def _extract_pages(file_path: str) -> list[tuple[int, str]]:
    """Return [(page_number, text)]. Requires PyMuPDF."""
    import fitz  # PyMuPDF, imported lazily

    pages = []
    with fitz.open(file_path) as doc:
        for i, page in enumerate(doc, start=1):
            pages.append((i, page.get_text("text")))
    return pages


def ingest_document(db: Session, document: Document) -> int:
    """(Re)index a document. Returns number of chunks written."""
    embedder = get_embedding_provider()

    # Deactivate previous chunks for this document (version rollover).
    db.execute(
        update(RagChunk)
        .where(RagChunk.document_id == document.id)
        .values(is_active=False)
    )

    new_version = (document.version or 1)

    # Collect every (page, chunk) first, then embed them all in ONE batched call.
    # Embedding per-chunk sequentially made an 80-page brochure take minutes and
    # time out; batching brings it down to seconds.
    items: list[tuple[int, str]] = []
    for page_no, page_text in _extract_pages(document.file_path):
        for chunk in _chunk_text(page_text):
            items.append((page_no, chunk))

    if not items:
        document.indexed_at = datetime.now(timezone.utc)
        document.status = "completed"
        db.commit()
        return 0

    vectors = embedder.embed([chunk for (_, chunk) in items])

    for (page_no, chunk), vector in zip(items, vectors):
        db.add(
            RagChunk(
                document_id=document.id,
                project_id=document.project_id,
                page=page_no,
                content=chunk,
                embedding=vector,
                version=new_version,
                is_active=True,
            )
        )

    document.indexed_at = datetime.now(timezone.utc)
    document.status = "completed"
    db.commit()
    return len(items)
