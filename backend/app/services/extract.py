"""
AI-assisted extraction of structured project data from a brochure PDF.

Gemini reads the brochure text and returns a JSON DRAFT (project attributes,
towers, configurations, payment plan). Nothing is saved — the draft goes to an
editable preview for a human (org-admin) to review before it enters SQL. The
prompt forbids inventing figures; unknown values come back null.
"""
from __future__ import annotations

import json

from app.services.llm import get_llm_provider
from app.services.llm.base import Message

SCHEMA_HINT = """{
  "name": string|null,
  "project_type": "Residential"|"Commercial"|"Industrial"|null,
  "land_parcel": string|null,          // e.g. "18 acres"
  "green_area": string|null,           // e.g. "72%"
  "project_status": "Under Construction"|"Ready to Move"|"Delivered"|"Launched"|null,
  "possession_date": "YYYY-MM-DD"|null,
  "towers": [ {"name": string, "floors": int|null, "height": string|null, "units_per_floor": int|null} ],
  "configurations": [ {"type": string, "carpet_area": number|null, "super_area": number|null,
                       "base_price": number|null, "price_unit": "per_sqft"|"total"|null,
                       "plc": number|null, "gst_percent": number|null} ],
  "payment_plan": {"name": string|null, "milestones": [ {"label": string, "percent": number} ]}
}"""

SYSTEM = (
    "You extract structured real-estate project data from brochure text. "
    "Reply with ONLY one valid JSON object matching the given schema — no prose, no markdown. "
    "NEVER invent figures: if a value is not clearly stated in the text, use null (or [] for lists). "
    "Write prices/areas as plain numbers (no commas, no currency symbols)."
)


def _parse_json(text: str) -> dict:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        t = t[i : j + 1]
    return json.loads(t)


def _normalize(d: dict) -> dict:
    """Ensure all keys exist with safe defaults for the preview form."""
    d = d if isinstance(d, dict) else {}
    return {
        "name": d.get("name"),
        "project_type": d.get("project_type"),
        "land_parcel": d.get("land_parcel"),
        "green_area": d.get("green_area"),
        "project_status": d.get("project_status"),
        "possession_date": d.get("possession_date"),
        "towers": d.get("towers") or [],
        "configurations": d.get("configurations") or [],
        "payment_plan": d.get("payment_plan") or {"name": None, "milestones": []},
    }


def extract_fields(pdf_text: str) -> dict:
    provider = get_llm_provider()
    if getattr(provider, "name", "") == "mock":
        return {"error": "Real AI (Gemini) required for extraction. Turn it on in Admin → AI Settings."}

    prompt = (
        "CONTEXT:\nExtract the fields below from this brochure. Use null for anything not stated.\n\n"
        f"SCHEMA:\n{SCHEMA_HINT}\n\nBROCHURE TEXT:\n{(pdf_text or '')[:12000]}\n\nReturn only the JSON object."
    )
    try:
        resp = provider.complete(
            system=SYSTEM,
            messages=[Message(role="user", content=prompt)],
            max_tokens=2048,
            temperature=0.0,
        )
        return {"draft": _normalize(_parse_json(resp.text))}
    except Exception as exc:
        return {"error": f"Could not parse AI output: {exc}"}
