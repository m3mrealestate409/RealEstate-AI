"""
Orchestration Core — the hybrid pipeline (Constitution §4).

    Query -> Intent -> Database -> Calculation -> RAG -> LLM -> Renderer

Golden Rule (§3): deterministic sources answer first; the LLM is the LAST
resort and only ever reasons over facts we already retrieved. It never invents
data. If nothing is found, we return the §8 'not available' message.
Every factual block carries a citation (§9).
"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.config import settings
from app.core.tenancy import org_scope_id
from app.models import QueryLog
from app.services import database_service as dbsvc
from app.services import intent as intent_svc
from app.services import nlparse, recommend, renderer
from app.services.llm import get_llm_provider
from app.services.llm.base import Message
from app.services.rag import retrieve as rag_retrieve
from app.services.session_memory import session_store

SYSTEM_PROMPT = (
    "You are a reliable real-estate company knowledge expert, NOT a creative chatbot. "
    "Use ONLY the facts in the CONTEXT. Never invent prices, payment plans, dates or any figures. "
    "Present whatever relevant facts the context DOES contain, clearly and concisely (use points/tables). "
    "If the user asks for one specific detail that is not in the context, say that detail isn't "
    "available — but still give the facts you do have. Reply exactly "
    "'Information not available in the current knowledge base.' ONLY when the context is entirely "
    "empty or irrelevant to the question. You may reply in English or Hindi/Hinglish to match the user."
)


def _confidence_for_db() -> float:
    return 0.98  # deterministic SQL fact


def _confidence_for_rag(chunks) -> float:
    if not chunks:
        return 0.0
    return round(min(0.95, max(c.similarity for c in chunks)), 2)


def handle_query(db: Session, query: str, session_id: str | None, user=None) -> dict:
    t0 = time.time()
    session_id = session_id or "anonymous"
    org_id = org_scope_id(user) if user is not None else None
    user_id = getattr(user, "id", None)
    prior_projects = session_store.last_project_ids(session_id)

    ir = intent_svc.detect(db, query, org_id=org_id, session_project_ids=prior_projects)

    # A project was named but doesn't exist in our data — never guess or reuse
    # the previous project's data (Constitution §8). Tell the user + suggest.
    if ir.unknown_project:
        from app.models import Project

        pq = db.query(Project).order_by(Project.name)
        if org_id is not None:
            pq = pq.filter(Project.organization_id == org_id)
        names = [p.name for p in pq.all()]
        block = renderer.paragraph_block(
            "Result",
            "Information not available in the current knowledge base. "
            + (f"Did you mean: {', '.join(names)}?" if names else ""),
        )
        env = _envelope(
            blocks=[block], citations=[], handlers=["none"], session_id=session_id,
            not_available=True, confidence=0.0, intent=ir, suggestions=names[:4],
        )
        _log_query(db, session_id=session_id, query=query, ir=ir, envelope=env,
                   latency_ms=int((time.time() - t0) * 1000), org_id=org_id, user_id=user_id)
        return env

    blocks: list[dict] = []
    citations: list[dict] = []
    context_for_llm: list[str] = []
    confidences: list[float] = []

    project_names = {p["id"]: p["name"] for p in ir.matched_projects}

    def name_of(pid: int) -> str:
        if pid in project_names:
            return project_names[pid]
        proj = dbsvc.get_project(db, pid)
        return proj.name if proj else f"Project {pid}"

    # ---- 1) DATABASE (SQL-first) -----------------------------------------
    for pid in ir.project_ids:
        pname = name_of(pid)
        for di in ir.db_intents:
            data = dbsvc.DB_RESOLVERS[di](db, pid)
            if data.get("found"):
                blocks.append(renderer.DB_BLOCK_BUILDERS[di](pname, data))
                citations.append(
                    {
                        "project": pname,
                        "source": f"Database ({di})",
                        "page": None,
                        "last_updated": data.get("last_updated"),
                        "confidence": _confidence_for_db(),
                    }
                )
                confidences.append(_confidence_for_db())
                context_for_llm.append(f"[{pname} {di}] {data}")

    # ---- 1b) COMPARISON (deterministic table across projects) ------------
    if "comparison" in ir.intents and len(ir.project_ids) >= 2:
        cols, rows = _comparison_table(db, ir.project_ids, name_of)
        blocks.append(renderer.comparison_block("Comparison", cols, rows))
        confidences.append(0.98)
        context_for_llm.append(f"[comparison] columns={cols} rows={rows}")

    # ---- 1c) RECOMMENDATION (deterministic shortlist) --------------------
    # Trigger on explicit intent, OR when a budget is stated without a specific
    # project (e.g. "3BHK under 2 crore").
    wants_reco = "recommendation" in ir.intents or (
        nlparse.parse_budget(query) is not None and not ir.project_ids
    )
    if wants_reco:
        config_type = nlparse.parse_config(query)
        budget = nlparse.parse_budget(query)
        matches = recommend.recommend(db, config_type=config_type, max_budget=budget, org_id=org_id)
        if matches:
            crit = []
            if config_type:
                crit.append(config_type)
            if budget:
                crit.append(f"under ₹{int(budget):,}")
            title = "Recommended" + (f" · {', '.join(crit)}" if crit else "")
            blocks.append(renderer.recommendation_block(title, matches))
            confidences.append(0.98)
            context_for_llm.append(f"[recommendations] {matches}")

    # ---- 2) RAG (documents only) -----------------------------------------
    if ir.rag_intents or ir.needs_llm:
        chunks = rag_retrieve.retrieve(
            db, query, project_ids=ir.project_ids or None, org_id=org_id
        )
        if chunks:
            title = "Documents"
            blocks.append(renderer.rag_block(f"From brochure — {title}", chunks))
            for c in chunks:
                citations.append(
                    {
                        "project": c.project_name,
                        "source": c.document_title or "Brochure",
                        "page": c.page,
                        "last_updated": None,
                        "confidence": c.similarity,
                    }
                )
                context_for_llm.append(
                    f"[{c.project_name} p{c.page}] {c.content}"
                )
            confidences.append(_confidence_for_rag(chunks))

    # ---- 3) LLM (reasoning only, grounded) -------------------------------
    if ir.needs_llm:
        provider = get_llm_provider()
        ctx = "\n".join(context_for_llm) if context_for_llm else ""
        user_msg = f"QUESTION: {query}\n\nCONTEXT:\n{ctx}"
        llm_resp = provider.complete(
            system=SYSTEM_PROMPT,
            messages=[Message(role="user", content=user_msg)],
        )
        primary_intent = next((i for i in ir.intents if i in intent_svc.LLM_INTENTS), "summary")
        blocks.append(renderer.paragraph_block(primary_intent.title(), llm_resp.text))
        # LLM confidence is capped by the weakest supporting source.
        confidences.append(round(min(confidences) if confidences else 0.4, 2))

    # ---- 4) Compose / Hallucination policy -------------------------------
    session_store.remember_turn(session_id, query=query, intents=ir.intents, project_ids=ir.project_ids)

    if not blocks:
        env = _envelope(
            blocks=[renderer.not_available_block()],
            citations=[],
            handlers=_handlers_used(ir),
            session_id=session_id,
            not_available=True,
            confidence=0.0,
            intent=ir,
            suggestions=_suggestions(ir),
        )
    else:
        overall_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        env = _envelope(
            blocks=blocks,
            citations=citations,
            handlers=_handlers_used(ir),
            session_id=session_id,
            not_available=False,
            confidence=overall_conf,
            intent=ir,
            suggestions=_suggestions(ir),
        )

    _log_query(db, session_id=session_id, query=query, ir=ir, envelope=env,
               latency_ms=int((time.time() - t0) * 1000), org_id=org_id, user_id=user_id)
    return env


def _comparison_table(db: Session, project_ids: list[int], name_of) -> tuple[list[str], list[list]]:
    """Build a side-by-side comparison from SQL facts (projects as columns)."""
    names = [name_of(pid) for pid in project_ids]
    columns = ["Field", *names]

    facts = {pid: {} for pid in project_ids}
    config_types: list[str] = []
    for pid in project_ids:
        st = dbsvc.status(db, pid)
        bd = dbsvc.builder(db, pid)
        pr = dbsvc.current_price(db, pid)
        facts[pid]["Status"] = st.get("project_status") if st.get("found") else "—"
        facts[pid]["Possession"] = st.get("possession_date") if st.get("found") else "—"
        facts[pid]["Builder"] = bd.get("builder") if bd.get("found") else "—"
        for row in pr.get("prices", []):
            key = f"{row['configuration']} price ({row['price_unit']})"
            facts[pid][key] = row["base_price"]
            if key not in config_types:
                config_types.append(key)

    rows: list[list] = []
    for field in ["Status", "Possession", "Builder", *config_types]:
        rows.append([field, *[facts[pid].get(field, "—") for pid in project_ids]])
    return columns, rows


def _suggestions(ir: intent_svc.IntentResult) -> list[str]:
    """Rule-based follow-up chips (no LLM cost). Contextual to the last project."""
    if not ir.project_ids:
        return ["Compare Golf Hills and Palm Greens", "Best 3BHK under 2 crore"]
    asked = set(ir.intents)
    pool = [
        ("price", "Price"),
        ("payment_plan", "Payment plan"),
        ("possession", "Possession"),
        ("inventory", "Inventory"),
        ("amenities", "Amenities"),
        ("offer", "Current offers"),
    ]
    return [label for key, label in pool if key not in asked][:4]


def _log_query(db: Session, *, session_id, query, ir, envelope, latency_ms, org_id=None, user_id=None) -> None:
    try:
        db.add(
            QueryLog(
                user_id=user_id,
                organization_id=org_id,
                session_id=session_id,
                query=query,
                intents=ir.intents,
                project_ids=ir.project_ids,
                handlers_used=envelope["handlers_used"],
                not_available=envelope["not_available"],
                confidence=envelope["confidence"],
                latency_ms=latency_ms,
            )
        )
        db.commit()
    except Exception:
        db.rollback()  # analytics logging must never break a query


def _handlers_used(ir: intent_svc.IntentResult) -> list[str]:
    used = []
    if ir.db_intents:
        used.append("database")
    if ir.rag_intents or ir.needs_llm:
        used.append("rag")
    if ir.needs_llm:
        used.append("llm")
    return used or ["none"]


def _envelope(*, blocks, citations, handlers, session_id, not_available, confidence, intent, suggestions=None) -> dict:
    answer_type = blocks[0]["type"] if len(blocks) == 1 else "composite"
    from app.services.runtime_config import get_llm_config

    # When a project was resolved from a misspelling, tell the user which one.
    note = None
    if intent.resolved_via in ("fuzzy", "llm") and intent.matched_projects:
        note = f"Showing results for {intent.matched_projects[0]['name']} (closest match to “{intent.candidate_phrase or intent.raw_query}”)."

    return {
        "answer_type": answer_type,
        "content": {"blocks": blocks},
        "citations": citations,
        "handlers_used": handlers,
        "session_id": session_id,
        "not_available": not_available,
        "confidence": confidence,
        "detected_intents": intent.intents,
        "resolved_from_memory": intent.resolved_from_memory,
        "resolved_via": intent.resolved_via,
        "resolution_note": note,
        "llm_provider": get_llm_config()["provider"],
        "suggestions": suggestions or [],
    }
