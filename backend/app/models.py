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
    project_status: Mapped[str | None] = mapped_column(String)  # Launched|Under Construction|Ready to Move
    launch_date: Mapped[date | None] = mapped_column(Date)
    possession_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    builder: Mapped["Builder"] = relationship(back_populates="projects")
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
