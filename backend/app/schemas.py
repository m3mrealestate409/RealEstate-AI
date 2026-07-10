"""Pydantic request/response schemas (API contracts)."""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str | None = None
    is_super_admin: bool = False
    organization_id: int | None = None


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None
    role: str
    tier: str = "basic"
    is_active: bool = True

    class Config:
        from_attributes = True


# --- Query (the engine) ---
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, examples=["Golf Hills 3BHK price and payment plan"])
    session_id: str | None = None


class Citation(BaseModel):
    project: str | None = None
    source: str | None = None
    page: int | None = None
    last_updated: str | None = None
    confidence: float | None = None


class QueryResponse(BaseModel):
    answer_type: str
    content: dict[str, Any]
    citations: list[Citation]
    handlers_used: list[str]
    session_id: str
    not_available: bool
    confidence: float
    detected_intents: list[str]
    resolved_from_memory: bool
    resolved_via: str = ""
    resolution_note: str | None = None
    llm_provider: str
    suggestions: list[str] = []
    limit_reached: bool = False
    cached: bool = False


# --- Calculation ---
class CalculationRequest(BaseModel):
    params: dict[str, Any]


class CalculationResponse(BaseModel):
    calc_type: str
    result: dict[str, Any]


# --- Projects (admin CRUD) ---
class ProjectCreate(BaseModel):
    name: str
    slug: str
    builder_id: int | None = None
    city: str | None = None
    locality: str | None = None
    rera_number: str | None = None
    project_status: str | None = None
    project_type: str | None = None
    land_parcel: str | None = None
    green_area: str | None = None
    launch_date: date | None = None
    possession_date: date | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    locality: str | None = None
    rera_number: str | None = None
    project_status: str | None = None
    project_type: str | None = None
    land_parcel: str | None = None
    green_area: str | None = None
    launch_date: date | None = None
    possession_date: date | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    slug: str
    city: str | None
    locality: str | None
    project_status: str | None
    project_type: str | None = None
    land_parcel: str | None = None
    green_area: str | None = None
    possession_date: date | None

    class Config:
        from_attributes = True


class TowerIn(BaseModel):
    name: str
    floors: int | None = None
    height: str | None = None
    units_per_floor: int | None = None


class TowerOut(TowerIn):
    id: int

    class Config:
        from_attributes = True
