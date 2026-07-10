"""
RAG retrieval: cosine similarity search over active chunks, filtered by project.

If nothing clears the similarity threshold, retrieval returns [] -> the
orchestrator emits the Hallucination-policy 'not available' message (§8)
instead of letting the LLM guess.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, RagChunk
from app.services.embeddings import get_embedding_provider


@dataclass
class RetrievedChunk:
    content: str
    project_id: int
    project_name: str | None
    document_title: str | None
    page: int | None
    similarity: float


def retrieve(
    db: Session,
    query: str,
    *,
    project_ids: list[int] | None = None,
    org_id: int | None = None,
    top_k: int | None = None,
    threshold: float | None = None,
) -> list[RetrievedChunk]:
    top_k = top_k or settings.rag_top_k

    embedder = get_embedding_provider()
    if threshold is None:
        # Mock embeddings are hash-based and weak; real (Gemini) embeddings
        # separate cleanly. Use a low floor for mock so RAG is usable in dev.
        threshold = 0.08 if embedder.name == "mock" else settings.rag_similarity_threshold

    q_vec = embedder.embed_one(query)

    # cosine distance -> similarity = 1 - distance
    distance = RagChunk.embedding.cosine_distance(q_vec).label("distance")
    stmt = (
        db.query(RagChunk, Document.title, distance)
        .join(Document, Document.id == RagChunk.document_id)
        .filter(RagChunk.is_active.is_(True))
    )
    if project_ids:
        stmt = stmt.filter(RagChunk.project_id.in_(project_ids))
    elif org_id is not None:
        # No specific project → still scope to the caller's org (tenant isolation).
        from app.models import Project

        stmt = stmt.join(Project, Project.id == RagChunk.project_id).filter(
            Project.organization_id == org_id
        )

    rows = stmt.order_by(distance).limit(top_k).all()

    results: list[RetrievedChunk] = []
    for chunk, doc_title, dist in rows:
        similarity = 1.0 - float(dist)
        if similarity < threshold:
            continue
        results.append(
            RetrievedChunk(
                content=chunk.content,
                project_id=chunk.project_id,
                project_name=chunk.document.project.name if chunk.document else None,
                document_title=doc_title,
                page=chunk.page,
                similarity=round(similarity, 4),
            )
        )
    return results
