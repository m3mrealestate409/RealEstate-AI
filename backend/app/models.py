"""
ORM models — the SQL-first source of truth (Constitution §5).

All volatile, structured facts (price, payment plan, inventory, possession,
RERA, builder, config, offers, dates) live here. NEVER only in PDFs.
Every fact-bearing table carries `updated_at` to satisfy the Citation Policy
(§9 "Last Updated Date").
"""
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base


# --------------------------------------------------------------------------
# Multi-tenancy: plans + organizations (the SaaS foundation)
# --------------------------------------------------------------------------
class Plan(Base):
    """A subscription tier. Limits are data-driven so plans can change without code."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # Basic | Advanced | …
    max_employees: Mapped[int] = mapped_column(Integer, default=5)
    daily_llm_quota: Mapped[int] = mapped_column(Integer, default=25)       # expensive queries / user / day
    price_monthly: Mapped[float] = mapped_column(Numeric, default=0)        # informational for now
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    organizations: Mapped[list["Organization"]] = relationship(back_populates="plan")


class Organization(Base):
    """A tenant — one real-estate company. All its users and projects are isolated."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Per-employee daily query limits for each tier (org-admin configurable).
    basic_daily_limit: Mapped[int] = mapped_column(Integer, default=25)
    advanced_daily_limit: Mapped[int] = mapped_column(Integer, default=100)
    # Editable greeting shown by the website chat widget (teaser + first message).
    widget_greeting: Mapped[str | None] = mapped_column(String)
    # Org-wide assistant persona/master prompt — applied to EVERY channel
    # (web app, website widget, CRM, WhatsApp). Controls voice/tone only; the
    # grounding rules (never invent facts) always stay on top.
    assistant_persona: Mapped[str | None] = mapped_column(Text)
    # Display identity for the chat widget (premium look): the assistant's name
    # (e.g. "Riya") and an optional avatar image path served from /static.
    assistant_name: Mapped[str | None] = mapped_column(String)
    assistant_avatar: Mapped[str | None] = mapped_column(String)
    # Optional CRM/webhook URL — every captured lead is POSTed here (best-effort)
    # so the company's own CRM receives it in real time. Provider-agnostic.
    crm_webhook_url: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plan: Mapped["Plan"] = relationship(back_populates="organizations")


# --------------------------------------------------------------------------
# People / org
# --------------------------------------------------------------------------
class Builder(Base):
    __tablename__ = "builders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    rera_id: Mapped[str | None] = mapped_column(String)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    projects: Mapped[list["Project"]] = relationship(back_populates="builder")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, nullable=False, default="sales")  # admin|manager|sales
    tier: Mapped[str] = mapped_column(String, default="basic")  # basic | advanced (query limit)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Multi-tenancy: org-scoped users; super-admins (SaaS owner) have no org.
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------
# Projects & structured facts
# --------------------------------------------------------------------------
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    builder_id: Mapped[int | None] = mapped_column(ForeignKey("builders.id"))
    city: Mapped[str | None] = mapped_column(String)
    locality: Mapped[str | None] = mapped_column(String)
    rera_number: Mapped[str | None] = mapped_column(String)
    project_status: Mapped[str | None] = mapped_column(String)  # Under Construction|Ready to Move|Delivered
    project_type: Mapped[str | None] = mapped_column(String)    # Residential|Commercial|Industrial
    land_parcel: Mapped[str | None] = mapped_column(String)     # e.g. "12 acres"
    green_area: Mapped[str | None] = mapped_column(String)      # e.g. "70%" or "8 acres"
    rise_type: Mapped[str | None] = mapped_column(String)       # High Rise | Mid Rise | Low Rise
    launch_date: Mapped[date | None] = mapped_column(Date)
    launch_price: Mapped[float | None] = mapped_column(Numeric) # launch/base sale price (₹/sq ft)
    possession_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    builder: Mapped["Builder"] = relationship(back_populates="projects")

    @property
    def builder_name(self) -> str | None:
        return self.builder.name if self.builder else None

    configurations: Mapped[list["Configuration"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    payment_plans: Mapped[list["PaymentPlan"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    offers: Mapped[list["Offer"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    towers: Mapped[list["Tower"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Tower.name"
    )
    location_points: Mapped[list["LocationPoint"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    amenities: Mapped[list["Amenity"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Amenity(Base):
    """A project amenity/facility (clubhouse, gym, pool…). SQL-first: extracted
    ONCE from the brochure at AI-import time, then always served from the DB —
    the LLM is never hit again for amenities."""

    __tablename__ = "amenities"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)             # "Swimming Pool", "Clubhouse"
    category: Mapped[str | None] = mapped_column(String)  # optional group: Sports | Leisure | Safety…

    project: Mapped["Project"] = relationship(back_populates="amenities")


class Tower(Base):
    """A tower/block within a project (per-tower height + floors)."""

    __tablename__ = "towers"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)              # "Tower A", "Block 1"
    floors: Mapped[int | None] = mapped_column(Integer)    # number of floors
    height: Mapped[str | None] = mapped_column(String)     # e.g. "150 m" / "G+40"
    units_per_floor: Mapped[int | None] = mapped_column(Integer)

    project: Mapped["Project"] = relationship(back_populates="towers")


class LocationPoint(Base):
    """A structured location highlight for a project (nearby place / connectivity /
    upcoming development), each with an optional distance."""

    __tablename__ = "location_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String)   # nearby | connectivity | upcoming
    name: Mapped[str] = mapped_column(String)       # "DPS School", "Dwarka Expressway"
    distance: Mapped[str | None] = mapped_column(String)  # "2 km", "10 min"
    notes: Mapped[str | None] = mapped_column(String)

    project: Mapped["Project"] = relationship(back_populates="location_points")


class Configuration(Base):
    __tablename__ = "configurations"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String)  # 2BHK, 3BHK, Villa, Plot
    carpet_area: Mapped[float | None] = mapped_column(Numeric)
    built_up_area: Mapped[float | None] = mapped_column(Numeric)
    super_area: Mapped[float | None] = mapped_column(Numeric)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="configurations")
    prices: Mapped[list["Price"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )
    inventory: Mapped["Inventory"] = relationship(
        back_populates="configuration", uselist=False, cascade="all, delete-orphan"
    )


class Price(Base):
    """Versioned price. `effective_to IS NULL` == current price."""

    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    configuration_id: Mapped[int] = mapped_column(ForeignKey("configurations.id", ondelete="CASCADE"))
    # Optional: price specific to a payment plan (real estate — the same config
    # can cost differently under CLP vs Down-Payment vs Subvention). NULL = the
    # base/default price that applies when no plan-specific price exists.
    payment_plan_id: Mapped[int | None] = mapped_column(ForeignKey("payment_plans.id"))
    base_price: Mapped[float] = mapped_column(Numeric, nullable=False)
    price_unit: Mapped[str] = mapped_column(String, default="per_sqft")  # per_sqft | total
    plc: Mapped[float | None] = mapped_column(Numeric)
    gst_percent: Mapped[float | None] = mapped_column(Numeric)
    effective_from: Mapped[date] = mapped_column(Date, server_default=func.now())
    effective_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String)  # e.g. 'Price List Jul-2026'
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    configuration: Mapped["Configuration"] = relationship(back_populates="prices")


class PaymentPlan(Base):
    __tablename__ = "payment_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)  # '10:80:10', 'CLP', 'Subvention'
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="payment_plans")
    milestones: Mapped[list["PaymentPlanMilestone"]] = relationship(
        back_populates="payment_plan", cascade="all, delete-orphan", order_by="PaymentPlanMilestone.sequence"
    )


class PaymentPlanMilestone(Base):
    __tablename__ = "payment_plan_milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_plan_id: Mapped[int] = mapped_column(ForeignKey("payment_plans.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String)  # 'On Booking', 'On Completion'
    percent: Mapped[float] = mapped_column(Numeric)

    payment_plan: Mapped["PaymentPlan"] = relationship(back_populates="milestones")


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    configuration_id: Mapped[int] = mapped_column(ForeignKey("configurations.id", ondelete="CASCADE"))
    total_units: Mapped[int | None] = mapped_column(Integer)
    available_units: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    configuration: Mapped["Configuration"] = relationship(back_populates="inventory")


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String)
    details: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    project: Mapped["Project"] = relationship(back_populates="offers")


# --------------------------------------------------------------------------
# Documents & RAG (Constitution §6 — document-only knowledge)
# --------------------------------------------------------------------------
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String)
    doc_type: Mapped[str | None] = mapped_column(String)  # brochure|legal|floor_plan|master_plan
    file_path: Mapped[str | None] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|processing|completed|failed
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship(back_populates="documents")
    chunks: Mapped[list["RagChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    page: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")


# --------------------------------------------------------------------------
# Audit (Constitution §19 — audit logging on all admin changes)
# --------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String)  # CREATE|UPDATE|DELETE
    entity: Mapped[str] = mapped_column(String)  # table name
    entity_id: Mapped[int | None] = mapped_column(Integer)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------
# API keys — machine-to-machine credentials for external integrations
# (CRM, WhatsApp bot, voice agent, other sites). Org-scoped; a request made
# with a key acts as the admin who created it, so tenant scoping still applies.
# --------------------------------------------------------------------------
class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String)                  # label, e.g. "CRM integration"
    prefix: Mapped[str] = mapped_column(String)                # e.g. "px_ab12cd" (shown in UI)
    key_hash: Mapped[str] = mapped_column(String, index=True)  # sha256 of the full key
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------
# Leads — a captured prospect from any channel (website widget, CRM, WhatsApp).
# The chatbot's whole point is to turn a conversation into a sales lead; this is
# where that contact lands. Org-scoped; optionally pushed to the org's CRM.
# --------------------------------------------------------------------------
class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    message: Mapped[str | None] = mapped_column(Text)             # what they asked / notes
    project_interest: Mapped[str | None] = mapped_column(String)  # project they were viewing
    source: Mapped[str] = mapped_column(String, default="widget") # widget | crm | whatsapp | app
    page_url: Mapped[str | None] = mapped_column(String)          # where they were on the site
    session_id: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="new")    # new | contacted | qualified | closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------
# Live chat — the agent-takeover feature. Every widget conversation is a
# ChatSession; each message (visitor, AI, or human agent) is a ChatMessage.
# When mode == "human", the AI stays silent and an employee handles the chat.
# --------------------------------------------------------------------------
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    session_id: Mapped[str] = mapped_column(String, index=True)  # the widget's session id
    mode: Mapped[str] = mapped_column(String, default="ai")      # ai | human
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # who took over
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("organization_id", "session_id", name="uq_chat_org_session"),)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_pk: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String)   # user | ai | agent | system
    text: Mapped[str] = mapped_column(Text)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------
# Runtime settings (server-side config, e.g. LLM provider + key).
# Keys NEVER leave the server; the frontend only sees masked status (§19).
# --------------------------------------------------------------------------
class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# --------------------------------------------------------------------------
# Query log — powers analytics (queries/day, popular projects, misses).
# --------------------------------------------------------------------------
class QueryLog(Base):
    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(String)
    query: Mapped[str] = mapped_column(Text)
    intents: Mapped[dict | None] = mapped_column(JSONB)
    project_ids: Mapped[dict | None] = mapped_column(JSONB)
    handlers_used: Mapped[dict | None] = mapped_column(JSONB)
    not_available: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Numeric)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
