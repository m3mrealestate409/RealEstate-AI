"""
Intent detection & entity linking (Constitution §4, §9 pipeline step 1).

Strategy: cheap deterministic rules first (keywords/regex) — no LLM cost for
the common case. Entities (project names) are fuzzy-matched against SQL. When
the query names no project, we fall back to session memory (§10) so follow-ups
resolve. Multi-intent is supported (e.g. price + amenities).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import Project

# Intent -> which handler answers it (drives the Golden-Rule router).
# Order matters: DB/calc intents are cheapest and checked first.
INTENT_KEYWORDS: dict[str, list[str]] = {
    # --- Database (SQL-first) ---
    "price": ["price", "cost", "rate", "kitne ka", "kitna", "daam", "keemat"],
    "payment_plan": ["payment plan", "payment", "installment", "emi plan", "10:80", "clp", "subvention", "plan"],
    "possession": ["possession", "handover", "ready", "kab milega", "delivery"],
    "inventory": ["inventory", "available", "units left", "stock", "availability", "bacha"],
    "builder": ["builder", "developer", "who is building", "kaun bana"],
    "status": ["status", "rera", "launch date", "launched", "under construction"],
    "offer": ["offer", "discount", "scheme", "deal"],
    # --- Calculation ---
    "calculation": ["calculate", "emi", "roi", "rental yield", "stamp duty", "total cost", "gst", "how much will"],
    # --- RAG (documents) ---
    "amenities": ["amenities", "facilities", "clubhouse", "club house", "swimming", "gym", "park"],
    "specifications": ["specification", "specs", "flooring", "fittings", "kitchen", "material"],
    "floor_plan": ["floor plan", "layout", "master plan", "site plan"],
    "legal": ["legal", "documents", "approval", "clearance"],
    # --- LLM reasoning ---
    "comparison": ["compare", "comparison", "vs", "versus", "difference", "better", "which one"],
    "summary": ["summary", "summarize", "overview", "tell me about", "brief"],
    "recommendation": ["recommend", "suggest", "should i", "best", "cheapest", "affordable",
                        "options", "budget", "which should", "show me"],
}

DB_INTENTS = {"price", "payment_plan", "possession", "inventory", "builder", "status", "offer"}
RAG_INTENTS = {"amenities", "specifications", "floor_plan", "legal"}
CALC_INTENTS = {"calculation"}
LLM_INTENTS = {"comparison", "summary", "recommendation"}


@dataclass
class IntentResult:
    intents: list[str] = field(default_factory=list)
    project_ids: list[int] = field(default_factory=list)
    matched_projects: list[dict] = field(default_factory=list)
    raw_query: str = ""
    resolved_from_memory: bool = False

    @property
    def needs_llm(self) -> bool:
        return bool(set(self.intents) & LLM_INTENTS)

    @property
    def db_intents(self) -> list[str]:
        return [i for i in self.intents if i in DB_INTENTS]

    @property
    def rag_intents(self) -> list[str]:
        return [i for i in self.intents if i in RAG_INTENTS]


def _detect_intents(query: str) -> list[str]:
    q = query.lower()
    found = []
    for intent, kws in INTENT_KEYWORDS.items():
        if any(kw in q for kw in kws):
            found.append(intent)
    return found


def _link_projects(db: Session, query: str) -> list[Project]:
    """Fuzzy-ish project linking. Uses trigram similarity when available,
    else a simple case-insensitive contains match."""
    q = query.lower()
    projects = db.query(Project).all()
    matches = []
    for p in projects:
        name = p.name.lower()
        # token overlap: any significant word of the project name in the query
        name_tokens = [t for t in re.split(r"\W+", name) if len(t) > 2]
        if name.lower() in q or any(tok in q for tok in name_tokens):
            matches.append(p)
    return matches


def detect(db: Session, query: str, *, session_project_ids: list[int] | None = None) -> IntentResult:
    intents = _detect_intents(query)
    projects = _link_projects(db, query)

    result = IntentResult(intents=intents, raw_query=query)
    if projects:
        result.project_ids = [p.id for p in projects]
        result.matched_projects = [{"id": p.id, "name": p.name} for p in projects]
    elif session_project_ids:
        # Follow-up question: reuse the project from conversation context (§10).
        result.project_ids = session_project_ids
        result.resolved_from_memory = True

    # If we detected a project but no clear intent, default to a summary.
    if result.project_ids and not intents:
        result.intents = ["summary"]

    return result
