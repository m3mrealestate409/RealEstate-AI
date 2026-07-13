"""
Orchestration Core — the hybrid pipeline (Constitution §4).

    Query -> Intent -> Database -> Calculation -> RAG -> LLM -> Renderer

Golden Rule (§3): deterministic sources answer first; the LLM is the LAST
resort and only ever reasons over facts we already retrieved. It never invents
data. If nothing is found, we return the §8 'not available' message.
Every factual block carries a citation (§9).
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date

from sqlalchemy.orm import Session

from app.config import settings
from app.core.tenancy import org_scope_id
from app.models import QueryLog
from app.services import database_service as dbsvc
from app.services import intent as intent_svc
from app.services import cache, nlparse, quota, recommend, renderer
from app.services.llm import get_llm_provider
from app.services.llm.base import Message
from app.services.rag import retrieve as rag_retrieve
from app.services.session_memory import session_store

SYSTEM_PROMPT = (
    "You are PropX, a sharp and friendly real-estate advisor helping a sales team answer client "
    "questions. Sound helpful, warm and confident — but crisp and to the point.\n\n"
    "GROUNDING (non-negotiable):\n"
    "- Use ONLY the facts given in CONTEXT. Never invent or guess prices, payment plans, dates, "
    "areas, or any figures.\n"
    "- If a specific detail the user asked for is missing from CONTEXT, briefly note it isn't "
    "available, but still present every relevant fact you DO have.\n"
    "- Reply with EXACTLY 'Information not available in the current knowledge base.' ONLY when the "
    "CONTEXT is entirely empty or irrelevant to the question.\n"
    "- When the user asks 'why buy / should I', you MAY frame the facts persuasively — but every "
    "single claim must come from CONTEXT.\n\n"
    "STYLE (write in Markdown):\n"
    "- Open with ONE short sentence that directly answers the question (a clear hook).\n"
    "- Then list the details as short bullet points, bolding the key term at the start of each, "
    "e.g. `- **Rooftop pool:** with skyline view`.\n"
    "- Keep it scannable and concise — no filler, no repetition, don't restate the question.\n"
    "- Match the user's language and tone (English, Hindi, or Hinglish).\n"
    "- Use Indian formatting for money that appears in CONTEXT (e.g. ₹1.2 crore, ₹9,800/sq ft)."
)


SMALLTALK_SYSTEM = (
    "You are a real-estate company's chat assistant talking to a website visitor. The user sent a "
    "greeting or small talk, not a data question. Reply warmly and briefly (1-2 sentences) in the "
    "user's language (English/Hindi/Hinglish), and gently invite them to ask about a project (price, "
    "payment plan, amenities) or to compare projects. NEVER invent prices, dates or figures. You may "
    "mention the listed project names."
)

_SMALLTALK = {
    "hi", "hii", "hello", "helo", "hey", "yo", "hola", "namaste", "namaskar", "hey there",
    "good morning", "good evening", "good afternoon", "how are you", "hows it going", "kaise ho",
    "kaise hain", "kya haal", "kaisa hai", "whats up", "sup", "thanks", "thank you", "thankyou",
    "dhanyavad", "dhanyawad", "shukriya", "ty", "ok", "okay", "okk", "theek hai", "thik hai",
    "achha", "acha", "great", "nice", "cool", "good", "bye", "goodbye", "alvida", "see you",
    "help", "madad", "who are you", "tum kaun ho", "aap kaun ho", "what can you do",
    "kya kar sakte ho", "what do you do",
}
_GREET_STARTS = {"hi", "hii", "hello", "helo", "hey", "namaste", "namaskar", "thanks", "thank",
                 "bye", "help", "madad", "good"}


def _is_smalltalk(query: str) -> bool:
    q = " ".join(query.lower().split()).strip(" ?!.,")
    if q in _SMALLTALK:
        return True
    words = q.split()
    return bool(words) and len(words) <= 3 and words[0] in _GREET_STARTS


logger = logging.getLogger(__name__)

# A 10-digit Indian mobile after separators are stripped — so ANY grouping the
# visitor might type (98765 43210, 9876 543210, 987-654-3210, +91 98765-43210)
# is caught. We favour recall: a missed number is a lost lead.
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91|0)?([6-9]\d{9})(?!\d)")
# Phrases that signal the visitor wants a human to reach out.
_CALLBACK_WORDS = (
    "call me", "callback", "call back", "phone me", "contact me", "reach me",
    "site visit", "book a visit", "book visit", "schedule a visit", "visit karna",
    "call karo", "call kijiye", "contact karo", "baat karni", "baat karna",
    "talk to someone", "talk to agent", "speak to", "sales team", "connect me",
)


def _extract_phone(query: str) -> str | None:
    """Return a normalised 10-digit phone if the text contains one. Common phone
    separators are stripped first so any grouping the visitor types is caught."""
    if not query:
        return None
    compact = re.sub(r"[\s\-.()]", "", query)  # 98765 43210 / 987-654-3210 → digits
    m = _PHONE_RE.search(compact)
    return m.group(1) if m else None


def _wants_callback(query: str) -> bool:
    q = (query or "").lower()
    return any(w in q for w in _CALLBACK_WORDS)


def _create_chat_lead(db, org_id, *, phone, query, session_id, project_name):
    """Auto-capture a lead when a website visitor drops their number in chat.
    Best-effort: a failure here must never break the answer."""
    from app.models import Lead, Organization

    try:
        lead = Lead(
            organization_id=org_id, phone=phone, message=query[:500],
            project_interest=project_name, source="widget", session_id=session_id,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        org = db.get(Organization, org_id) if org_id else None
        if org and org.crm_webhook_url:
            _push_lead_to_crm(org.crm_webhook_url, {
                "id": lead.id, "phone": phone, "message": query[:500],
                "project_interest": project_name, "source": "widget",
            })
        return lead
    except Exception as exc:  # noqa: BLE001
        logger.warning("Auto chat-lead capture failed: %s", exc)
        db.rollback()
        return None


def _push_lead_to_crm(url: str, payload: dict) -> None:
    try:
        import httpx

        httpx.post(url, json=payload, timeout=8.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CRM webhook push failed: %s", exc)


def _system_with_persona(base: str, persona: str | None) -> str:
    """Prepend the org's persona (voice/style) — the grounding rules in `base`
    always stay on top, so tone changes but facts never get invented."""
    if persona:
        return "PERSONA — adopt this identity, voice and style in every reply:\n" + persona.strip() + "\n\n" + base
    return base


def _get_persona(db: Session, org_id: int | None) -> str | None:
    if not org_id:
        return None
    from app.models import Organization

    org = db.get(Organization, org_id)
    return org.assistant_persona if org and org.assistant_persona else None


def _dialogue_context(mem_key: str, max_turns: int = 4) -> str:
    """Recent conversation as a compact transcript for the LLM, so replies can
    reference earlier turns naturally (per-session memory). Facts still come
    only from the grounded CONTEXT — this is for continuity, not truth."""
    lines: list[str] = []
    for t in session_store.recent_dialogue(mem_key, max_turns):
        q = (t.get("query") or "").strip()
        a = (t.get("answer") or "").strip()
        if q:
            lines.append("User: " + q)
        if a:
            lines.append("Assistant: " + a)
    return "\n".join(lines)


def _persona_smalltalk(query: str, persona: str | None, names: list[str], history: str = "") -> str:
    from app.services.runtime_config import get_llm_config

    if get_llm_config().get("provider") == "mock":
        msg = "Hi! I can help with our projects — ask about price, payment plan, amenities, or compare two."
        return msg + (" For example: " + ", ".join(names[:3]) + "." if names else "")
    ctx = ("Known projects: " + ", ".join(names)) if names else "No projects are listed yet."
    user_content = ""
    if history:
        user_content += "RECENT CONVERSATION (for context, not facts):\n" + history + "\n\n"
    user_content += "CONTEXT: " + ctx + "\n\nUser said: " + query
    try:
        resp = get_llm_provider().complete(
            system=_system_with_persona(SMALLTALK_SYSTEM, persona),
            messages=[Message(role="user", content=user_content)],
            max_tokens=256,
        )
        return (resp.text or "").strip() or "Hi! How can I help you with our projects?"
    except Exception:
        return "Hi! How can I help you with our projects?"


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
    today = date.today().isoformat()
    persona = _get_persona(db, org_id)  # org-wide voice/style for every channel

    # H1 — session memory is keyed to the authenticated user, NOT just the
    # client-supplied session_id, so one user can never inherit another user's
    # (or another tenant's) conversation context by guessing/fixing a session id.
    mem_key = f"u{user_id}:{session_id}" if user_id is not None else session_id
    prior_projects = session_store.last_project_ids(mem_key)
    prior_dialogue = _dialogue_context(mem_key)  # recent turns → natural multi-turn replies
    wants_cb = _wants_callback(query)  # visitor asked to be contacted / book a visit

    ir = intent_svc.detect(db, query, org_id=org_id, session_project_ids=prior_projects)

    # H1 (defence in depth) — regardless of where project_ids came from (intent
    # match OR session memory), keep only projects that belong to the caller's
    # org before any SQL/RAG lookup. Closes cross-tenant reads on every path.
    if org_id is not None and ir.project_ids:
        from app.models import Project

        owned = {
            pid
            for (pid,) in db.query(Project.id)
            .filter(Project.id.in_(ir.project_ids), Project.organization_id == org_id)
            .all()
        }
        ir.project_ids = [p for p in ir.project_ids if p in owned]
        ir.matched_projects = [m for m in ir.matched_projects if m["id"] in owned]

    # Website visitor dropped their phone number in chat → capture a lead right
    # away and reply warmly. Only for external channels (API key) — a logged-in
    # employee (JWT) typing a number must NOT create a lead.
    if getattr(user, "_via_api_key", False) and org_id is not None:
        phone = _extract_phone(query)
        if phone:
            pname = None
            if prior_projects:
                p = dbsvc.get_project(db, prior_projects[0])
                pname = p.name if p else None
            _create_chat_lead(db, org_id, phone=phone, query=query,
                               session_id=session_id, project_name=pname)
            msg = ("Thank you! 🙌 I've noted your number"
                   + (f" — and your interest in **{pname}**" if pname else "")
                   + ". Our team will call you back shortly. Meanwhile, feel free to ask me "
                   "anything about our projects — price, payment plan, or amenities.")
            env = _envelope(
                blocks=[renderer.paragraph_block("", msg)],
                citations=[], handlers=["assistant"], session_id=session_id,
                not_available=False, confidence=0.9, intent=ir, suggestions=[],
            )
            env["lead_captured"] = True
            if user is not None:
                quota.consume_quota(user, today, org_id)
            session_store.remember_turn(mem_key, query=query, intents=ir.intents,
                                        project_ids=ir.project_ids, answer=msg)
            _log_query(db, session_id=session_id, query=query, ir=ir, envelope=env,
                       latency_ms=int((time.time() - t0) * 1000), org_id=org_id, user_id=user_id)
            return env

    # Small talk / greeting → a warm persona chat reply (no factual claims). Makes
    # the assistant feel like an agent instead of a search box.
    if _is_smalltalk(query) and not ir.project_ids and not ir.db_intents and not ir.rag_intents and not ir.needs_llm:
        from app.models import Project

        pq = db.query(Project).order_by(Project.name)
        if org_id is not None:
            pq = pq.filter(Project.organization_id == org_id)
        names = [p.name for p in pq.all()]
        reply = _persona_smalltalk(query, persona, names, history=prior_dialogue)
        env = _envelope(
            blocks=[renderer.paragraph_block("", reply)],
            citations=[], handlers=["assistant"], session_id=session_id,
            not_available=False, confidence=0.6, intent=ir, suggestions=names[:4],
        )
        if user is not None:
            quota.consume_quota(user, today, org_id)
        session_store.remember_turn(mem_key, query=query, intents=ir.intents,
                                    project_ids=ir.project_ids, answer=reply)
        _log_query(db, session_id=session_id, query=query, ir=ir, envelope=env,
                   latency_ms=int((time.time() - t0) * 1000), org_id=org_id, user_id=user_id)
        return env

    # A project was named but doesn't exist in our data. We never reuse the
    # previous project's data (§8), but we CAN offer an unverified general-
    # knowledge answer + suggest the known projects.
    if ir.unknown_project:
        from app.models import Project

        pq = db.query(Project).order_by(Project.name)
        if org_id is not None:
            pq = pq.filter(Project.organization_id == org_id)
        names = [p.name for p in pq.all()]
        fb = _internet_fallback(query, persona, history=prior_dialogue)
        if fb:
            env = _envelope(
                blocks=[renderer.paragraph_block("Answer (general knowledge)", fb)],
                citations=[], handlers=["internet"], session_id=session_id,
                not_available=False, confidence=0.3, intent=ir, suggestions=names[:4],
            )
            env["unverified"] = True
            if user is not None:
                quota.consume_quota(user, today, org_id)
        else:
            block = renderer.paragraph_block(
                "Result",
                "Information not available in the current knowledge base. "
                + (f"Did you mean: {', '.join(names)}?" if names else ""),
            )
            env = _envelope(
                blocks=[block], citations=[], handlers=["none"], session_id=session_id,
                not_available=True, confidence=0.0, intent=ir, suggestions=names[:4],
            )
        env["suggest_callback"] = bool(wants_cb or env.get("not_available"))
        _log_query(db, session_id=session_id, query=query, ir=ir, envelope=env,
                   latency_ms=int((time.time() - t0) * 1000), org_id=org_id, user_id=user_id)
        return env

    # ---- CACHE + QUOTA: only EXPENSIVE (LLM/RAG) queries; SQL look-ups are free.
    is_expensive = bool(ir.rag_intents or ir.needs_llm)
    cacheable = is_expensive and not ir.resolved_from_memory  # follow-ups depend on context

    if is_expensive:
        # 1) Serve a cached answer if we have one — no LLM call, no quota spent.
        if cacheable:
            hit = cache.get(org_id, query)
            if hit is not None:
                hit = dict(hit)
                hit["cached"] = True
                hit["session_id"] = session_id
                session_store.remember_turn(
                    mem_key, query=query, intents=ir.intents, project_ids=ir.project_ids,
                    answer=renderer.blocks_to_text(hit.get("content", {}).get("blocks", [])),
                )
                _log_query(db, session_id=session_id, query=query, ir=ir, envelope=hit,
                           latency_ms=int((time.time() - t0) * 1000), org_id=org_id, user_id=user_id)
                return hit

        # 2) Enforce per-employee tier limit AND company-wide plan quota.
        if user is not None:
            u_ok, _, u_limit = quota.check_quota(db, user, today)
            o_ok, _, o_limit = quota.check_org_quota(db, org_id, today)
            if not u_ok or not o_ok:
                if not o_ok:
                    text = (f"Your company's daily AI quota ({o_limit}) is used up for today. "
                            "Price/inventory look-ups still work. Ask your admin to upgrade the plan.")
                else:
                    text = (f"You've used all {u_limit} of your AI queries for today (your tier: {user.tier}). "
                            "Price/inventory look-ups still work. Ask your admin to raise your limit.")
                env = _envelope(
                    blocks=[renderer.paragraph_block("Daily limit reached", text)],
                    citations=[], handlers=["quota"], session_id=session_id,
                    not_available=True, confidence=0.0, intent=ir, suggestions=[],
                )
                env["limit_reached"] = True
                _log_query(db, session_id=session_id, query=query, ir=ir, envelope=env,
                           latency_ms=int((time.time() - t0) * 1000), org_id=org_id, user_id=user_id)
                return env
            quota.consume_quota(user, today, org_id)  # count this expensive query

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
            # Show the raw brochure excerpt ONLY when the LLM won't summarize it.
            # When there IS a summary, the (nicely formatted) summary + the source
            # citation already cover it — the raw run-on excerpt is just noise.
            if not ir.needs_llm:
                blocks.append(renderer.rag_block("From brochure", chunks))

    # ---- 3) LLM (reasoning only, grounded) -------------------------------
    if ir.needs_llm:
        provider = get_llm_provider()
        ctx = "\n".join(context_for_llm) if context_for_llm else ""
        user_msg = ""
        if prior_dialogue:
            user_msg += "RECENT CONVERSATION (context only — never treat as facts):\n" + prior_dialogue + "\n\n"
        user_msg += f"QUESTION: {query}\n\nCONTEXT:\n{ctx}"
        llm_resp = provider.complete(
            system=_system_with_persona(SYSTEM_PROMPT, persona),
            messages=[Message(role="user", content=user_msg)],
        )
        primary_intent = next((i for i in ir.intents if i in intent_svc.LLM_INTENTS), "summary")
        blocks.append(renderer.paragraph_block(primary_intent.title(), llm_resp.text))
        # LLM confidence is capped by the weakest supporting source.
        confidences.append(round(min(confidences) if confidences else 0.4, 2))

    # ---- 4) Compose / Hallucination policy -------------------------------
    if not blocks:
        # Nothing in the company knowledge base — fall back to the LLM's general
        # knowledge, clearly flagged as UNVERIFIED (red badge in the UI).
        fb = _internet_fallback(query, persona, history=prior_dialogue) if not ir.unknown_project else None
        if fb:
            env = _envelope(
                blocks=[renderer.paragraph_block("Answer (general knowledge)", fb)],
                citations=[], handlers=["internet"], session_id=session_id,
                not_available=False, confidence=0.3, intent=ir, suggestions=_suggestions(ir),
            )
            env["unverified"] = True
            if user is not None:
                quota.consume_quota(user, today, org_id)  # it's a real LLM call
        else:
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

    # Offer a callback when the visitor asked to be contacted, or when we
    # couldn't answer (a natural moment to hand off to the sales team). Set
    # BEFORE caching so a cache hit preserves the flag.
    env["suggest_callback"] = bool(wants_cb or env.get("not_available"))

    # Cache a fresh, self-contained expensive answer for repeat queries.
    if blocks and cacheable:
        cache.set(org_id, query, env)

    # Record this turn (query + answer) so the next turn has conversation context.
    session_store.remember_turn(
        mem_key, query=query, intents=ir.intents, project_ids=ir.project_ids,
        answer=renderer.blocks_to_text(env.get("content", {}).get("blocks", [])),
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


INTERNET_SYSTEM = (
    "You are PropX, a friendly real-estate assistant. The company's own database has NO record for "
    "this question, so answer from your GENERAL knowledge.\n"
    "STYLE (Markdown): open with one direct sentence, then short bullet points with the key term "
    "bolded; be concise and useful; match the user's language (English/Hindi/Hinglish).\n"
    "CRITICAL: if you are not certain about a specific local project or an exact figure (especially a "
    "price), clearly say you are not sure — NEVER invent a precise number, price, or date. General "
    "context is better than a made-up fact."
)


def _internet_fallback(query: str, persona: str | None = None, history: str = "") -> str | None:
    """Last-resort answer from the LLM's general knowledge (unverified). Skipped
    in mock mode. The answer is always flagged unverified to the user."""
    from app.services.runtime_config import get_llm_config

    if get_llm_config().get("provider") == "mock":
        return None
    user_content = query
    if history:
        user_content = "RECENT CONVERSATION (context only):\n" + history + "\n\nUser said: " + query
    try:
        resp = get_llm_provider().complete(
            system=_system_with_persona(INTERNET_SYSTEM, persona),
            messages=[Message(role="user", content=user_content)],
            max_tokens=1024,
        )
        text = (resp.text or "").strip()
        return text or None
    except Exception:
        return None


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
        "cached": False,
        "unverified": False,
        # UI signals for chat channels: whether to nudge/open the callback form,
        # and whether this reply already captured a lead.
        "suggest_callback": False,
        "lead_captured": False,
    }
