"""
Intent detection & entity linking (Constitution §4, §9 pipeline step 1).

Project linking is LAYERED (Golden Rule: cheap deterministic first, LLM last):
  1. Exact whole-word match     — correct spelling, instant, no false positives.
  2. Fuzzy match                — typo tolerance (works offline, no key needed).
  3. LLM disambiguation         — hard cases/abbreviations, only when a real
                                  provider is configured and 1 & 2 failed.

Crucially, we distinguish a *bare follow-up* ("possession?" → use session memory)
from an *unknown project reference* ("gic price" → say "not available", never
silently answer for the previous project). Multi-intent is supported.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models import Project

# Intent -> which handler answers it (drives the Golden-Rule router).
INTENT_KEYWORDS: dict[str, list[str]] = {
    # --- Database (SQL-first) ---
    "price": ["price", "cost", "rate", "kitne ka", "kitna", "daam", "keemat"],
    "payment_plan": ["payment plan", "payment", "installment", "emi plan", "10:80", "clp", "subvention", "plan"],
    "possession": ["possession", "handover", "ready", "kab milega", "delivery"],
    "inventory": ["inventory", "available", "units left", "stock", "availability", "bacha"],
    "builder": ["builder", "developer", "who is building", "kaun bana"],
    "status": ["status", "rera", "launch date", "launched", "under construction", "delivered"],
    "offer": ["offer", "discount", "scheme", "deal"],
    "overview": ["land parcel", "land area", "acre", "towers", "tower", "floors", "height",
                 "green area", "open area", "residential", "commercial", "industrial",
                 "project type", "details", "how many towers"],
    "location": ["location", "nearby", "near by", "surrounding", "surroundings", "around",
                 "aas paas", "connectivity", "metro", "airport", "highway", "expressway",
                 "distance", "upcoming", "development around", "what's near", "whats near"],
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

# amenities is SQL-first (extracted once at import, then served from the DB — the
# LLM is never hit for it), so it lives in DB_INTENTS, not RAG_INTENTS.
DB_INTENTS = {"price", "payment_plan", "possession", "inventory", "builder", "status",
              "offer", "overview", "location", "amenities"}
RAG_INTENTS = {"specifications", "floor_plan", "legal"}
CALC_INTENTS = {"calculation"}
LLM_INTENTS = {"comparison", "summary", "recommendation"}

FUZZY_THRESHOLD = 0.72       # min similarity to accept a typo'd project name
LLM_ASSIST_FLOOR = 0.45      # only spend an LLM call when fuzzy is a near-miss

# Words that are NOT part of a project name — stripped to isolate the
# "candidate project phrase" from the rest of the query.
_INTENT_TOKENS = {w for kws in INTENT_KEYWORDS.values() for kw in kws for w in kw.split()}
_STOPWORDS = {
    "the", "of", "is", "a", "an", "what", "whats", "does", "do", "did", "have", "has",
    "for", "in", "on", "at", "and", "or", "me", "my", "to", "with", "about", "tell",
    "give", "want", "need", "please", "show", "get", "current", "latest", "this",
    "ka", "ke", "ki", "kya", "hai", "ha", "batao", "bata", "kaunsa", "konsa", "mujhe",
    "cr", "crore", "lakh", "lac", "rupees", "rs", "under", "villa", "plot",
}


@dataclass
class IntentResult:
    intents: list[str] = field(default_factory=list)
    project_ids: list[int] = field(default_factory=list)
    matched_projects: list[dict] = field(default_factory=list)
    raw_query: str = ""
    resolved_from_memory: bool = False
    resolved_via: str = ""          # exact | fuzzy | llm | memory | ""
    unknown_project: bool = False   # a project was named but couldn't be resolved
    candidate_phrase: str = ""

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


def _candidate_phrase(query: str) -> str:
    """Whatever remains after removing intent keywords, stopwords, configs and
    numbers — i.e. the part that could be a project name."""
    q = query.lower()
    q = re.sub(r"\b\d+\s*bhk\b", " ", q)   # drop "3bhk"
    words = re.findall(r"[a-z0-9]+", q)
    keep = [w for w in words if w not in _INTENT_TOKENS and w not in _STOPWORDS and not w.isdigit()]
    return " ".join(keep).strip()


def _fuzzy_score(candidate: str, name: str) -> float:
    """Similarity between the candidate phrase and a project name (typo-tolerant)."""
    full = SequenceMatcher(None, candidate, name).ratio()
    tok_best = 0.0
    for ct in candidate.split():
        for nt in name.split():
            tok_best = max(tok_best, SequenceMatcher(None, ct, nt).ratio())
    return max(full, tok_best * 0.95)


def _llm_resolve(query: str, projects: list[Project]) -> Project | None:
    """Layer 3: ask the LLM to map the query to a known project. Skipped in mock
    mode (no key) so it costs nothing until a real provider is configured."""
    from app.services.runtime_config import get_llm_config

    if get_llm_config().get("provider") == "mock":
        return None
    from app.services.llm import get_llm_provider
    from app.services.llm.base import Message

    names = [p.name for p in projects]
    prompt = (
        f"User asked: \"{query}\".\nAvailable projects: {names}.\n"
        "Which ONE project name from the list does the user most likely mean "
        "(handle typos and abbreviations)? Reply with the EXACT project name from "
        "the list, or the word NONE if you cannot tell. Never invent a name."
    )
    try:
        resp = get_llm_provider().complete(
            system="You map a user's query to a fixed list of real-estate project names. If unsure, reply NONE.",
            messages=[Message(role="user", content="CONTEXT: " + prompt)],
            max_tokens=30,
        )
        ans = (resp.text or "").strip().lower()
        for p in projects:
            if p.name.lower() in ans:
                return p
    except Exception:
        pass
    return None


def link_projects(db: Session, query: str, org_id: int | None = None) -> tuple[list[Project], str]:
    """Return (matched_projects, how). `how` ∈ exact | fuzzy | llm | followup | unknown.
    Scoped to `org_id` (None = super-admin, all orgs)."""
    pq = db.query(Project)
    if org_id is not None:
        pq = pq.filter(Project.organization_id == org_id)
    projects = pq.all()
    q = query.lower()
    query_words = set(re.findall(r"[a-z0-9]+", q))

    # Layer 1 — exact whole-word (full name present, or all name-words present).
    exact = []
    for p in projects:
        name = p.name.lower()
        name_words = set(re.findall(r"[a-z0-9]+", name))
        if name in q or (name_words and name_words <= query_words):
            exact.append(p)
    if exact:
        return exact, "exact"

    candidate = _candidate_phrase(query)
    if not candidate:
        return [], "followup"   # bare follow-up — caller may use session memory

    # Layer 2 — fuzzy (typo tolerance, offline).
    best, best_score = None, 0.0
    for p in projects:
        score = _fuzzy_score(candidate, p.name.lower())
        if score > best_score:
            best_score, best = score, p
    if best and best_score >= FUZZY_THRESHOLD:
        return [best], "fuzzy"

    # Layer 3 — LLM disambiguation, but ONLY when fuzzy was a near-miss (a
    # plausible typo). Clearly-unrelated queries skip the LLM entirely so we
    # don't waste an API call (cost) or block on a slow/rate-limited response.
    if best_score >= LLM_ASSIST_FLOOR:
        llm_match = _llm_resolve(query, projects)
        if llm_match:
            return [llm_match], "llm"

    return [], "unknown"   # named something, but it's not a known project


def detect(db: Session, query: str, *, org_id: int | None = None, session_project_ids: list[int] | None = None) -> IntentResult:
    intents = _detect_intents(query)
    matched, how = link_projects(db, query, org_id)

    result = IntentResult(intents=intents, raw_query=query, candidate_phrase=_candidate_phrase(query))

    if matched:
        result.project_ids = [p.id for p in matched]
        result.matched_projects = [{"id": p.id, "name": p.name} for p in matched]
        result.resolved_via = how
    elif how == "unknown":
        # A project was named but is not in our data — do NOT reuse memory (§8).
        result.unknown_project = True
    elif session_project_ids:
        # Bare follow-up: reuse the project from conversation context (§10).
        result.project_ids = session_project_ids
        result.resolved_from_memory = True
        result.resolved_via = "memory"

    # If we resolved a project but no clear intent, default to a summary.
    if result.project_ids and not intents:
        result.intents = ["summary"]

    return result
