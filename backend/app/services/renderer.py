"""
Response Renderer (Constitution §16, §17).

Turns collected facts into render-ready blocks, choosing the easiest format:
Cards > Tables > Timeline > Checklist > Paragraph. The client just renders
what the engine returns. Never long paragraphs when data is structured.
"""
from __future__ import annotations

import re


def price_block(project_name: str, data: dict) -> dict:
    rows = []
    for r in data.get("prices", []):
        plans = r.get("plans") or []
        # Show the base row unless the config has ONLY plan-specific prices.
        if r.get("base_price") is not None or not plans:
            rows.append([
                r["configuration"],
                "BSP",
                r.get("base_price"),
                r.get("size"),
                r.get("price_unit"),
                r.get("plc"),
                r.get("gst_percent"),
            ])
        for pl in plans:
            rows.append([
                r["configuration"],
                pl["plan"],
                pl["base_price"],
                r.get("size"),
                pl["price_unit"],
                pl.get("plc"),
                pl.get("gst_percent"),
            ])
    return {
        "type": "table",
        "title": f"{project_name} - Price",
        "columns": ["Configuration", "Plan", "Base Price", "Size", "Unit", "PLC", "GST %"],
        "rows": rows,
    }


def payment_plan_block(project_name: str, data: dict) -> dict:
    plans = data.get("payment_plans", [])
    return {
        "type": "card",
        "title": f"{project_name} - Payment Plan",
        "cards": [
            {
                "heading": p["name"],
                "subtitle": p.get("description"),
                "items": [f"{m['label']}: {m['percent']}%" for m in p.get("milestones", [])],
            }
            for p in plans
        ],
    }


def inventory_block(project_name: str, data: dict) -> dict:
    return {
        "type": "table",
        "title": f"{project_name} - Inventory",
        "columns": ["Configuration", "Total Units", "Available"],
        "rows": [
            [r["configuration"], r["total_units"], r["available_units"]]
            for r in data.get("inventory", [])
        ],
    }


def possession_block(project_name: str, data: dict) -> dict:
    return {
        "type": "timeline",
        "title": f"{project_name} - Possession",
        "events": [
            {"label": "Status", "value": data.get("project_status")},
            {"label": "Possession", "value": data.get("possession_date")},
        ],
    }


def builder_block(project_name: str, data: dict) -> dict:
    return {
        "type": "card",
        "title": f"{project_name} - Developer",
        "cards": [{"heading": data.get("builder"), "items": [f"RERA: {data.get('rera_id') or 'N/A'}"]}],
    }


def status_block(project_name: str, data: dict) -> dict:
    return {
        "type": "card",
        "title": f"{project_name} - Status",
        "cards": [
            {
                "heading": data.get("project_status") or "Unknown",
                "items": [
                    f"RERA: {data.get('rera_number') or 'N/A'}",
                    f"Launch: {data.get('launch_date') or 'N/A'}",
                    f"Possession: {data.get('possession_date') or 'N/A'}",
                ],
            }
        ],
    }


def offer_block(project_name: str, data: dict) -> dict:
    return {
        "type": "checklist",
        "title": f"{project_name} - Offers",
        "items": [f"{o['title']} - {o.get('details') or ''}" for o in data.get("offers", [])],
    }


def overview_block(project_name: str, data: dict) -> dict:
    items = []
    if data.get("project_type"):
        items.append(f"Type: {data['project_type']}")
    if data.get("land_parcel"):
        items.append(f"Land parcel: {data['land_parcel']}")
    if data.get("green_area"):
        items.append(f"Green/open area: {data['green_area']}")
    if data.get("project_status"):
        items.append(f"Status: {data['project_status']}")
    items.append(f"Total towers: {data.get('total_towers', 0)}")
    cards = [{"heading": f"{project_name} - Overview", "items": items}]
    towers = data.get("towers") or []
    if towers:
        cards.append({
            "heading": "Towers",
            "items": [
                f"{t['name']}: {t.get('floors') or '—'} floors"
                + (f", {t['height']}" if t.get("height") else "")
                for t in towers
            ],
        })
    return {"type": "card", "title": f"{project_name} - Overview", "cards": cards}


def location_block(project_name: str, data: dict) -> dict:
    groups = [
        ("Nearby", data.get("nearby") or []),
        ("Connectivity", data.get("connectivity") or []),
        ("Upcoming Development", data.get("upcoming") or []),
    ]
    cards = []
    for label, points in groups:
        if not points:
            continue
        cards.append({
            "heading": label,
            "items": [
                p["name"] + (f" — {p['distance']}" if p.get("distance") else "")
                + (f" ({p['notes']})" if p.get("notes") else "")
                for p in points
            ],
        })
    if not cards:
        cards = [{"heading": "Location", "items": [f"{data.get('locality') or ''}, {data.get('city') or ''}"]}]
    return {"type": "card", "title": f"{project_name} - Location & Connectivity", "cards": cards}


def amenities_block(project_name: str, data: dict) -> dict:
    grouped = data.get("grouped") or {}
    if grouped:
        cards = [{"heading": cat, "items": names} for cat, names in grouped.items()]
    else:
        cards = [{"heading": "Amenities", "items": data.get("amenities", [])}]
    return {"type": "card", "title": f"{project_name} - Amenities", "cards": cards}


_BULLET_SPLIT = re.compile(r"(?:\s+[-–—•·]\s+|\s*[;\n]+\s*)")


def _to_bullets(text: str) -> list[str]:
    """Break a whitespace-collapsed brochure chunk into readable bullet lines.
    Brochure PDFs put ' - ' / '•' between points; those separators survive
    chunking, so we split a run-on excerpt into scannable items (falls back to
    the whole text if there are no separators)."""
    parts = [p.strip(" -–—•·\t:").strip() for p in _BULLET_SPLIT.split(text or "")]
    parts = [p for p in parts if p]
    return parts or ([text.strip()] if text and text.strip() else [])


def rag_block(title: str, chunks: list) -> dict:
    items: list[str] = []
    for c in chunks:
        items.extend(_to_bullets(c.content))
    return {"type": "checklist", "title": title, "items": items}


def paragraph_block(title: str, text: str) -> dict:
    return {"type": "paragraph", "title": title, "text": text}


def comparison_block(title: str, columns: list[str], rows: list[list]) -> dict:
    # Rendered as a table with the first column being the field name.
    return {"type": "table", "title": title, "columns": columns, "rows": rows}


def recommendation_block(title: str, matches: list[dict]) -> dict:
    def money(n):
        return f"₹{int(n):,}" if n is not None else "—"

    return {
        "type": "card",
        "title": title,
        "cards": [
            {
                "heading": f"{m['project']} · {m['configuration']}",
                "subtitle": money(m["total_price"]),
                "items": [
                    f"Status: {m.get('status') or '—'}",
                    f"Possession: {m.get('possession') or '—'}",
                ],
            }
            for m in matches
        ],
    }


def not_available_block(title: str = "Result") -> dict:
    return {
        "type": "paragraph",
        "title": title,
        "text": "Information not available in the current knowledge base.",
    }


def blocks_to_text(blocks: list[dict], voice: bool = False) -> str:
    """Flatten answer blocks into a plain-text answer for non-UI consumers
    (CRM inline, WhatsApp, voice). `voice=True` strips Markdown and keeps it short."""
    lines: list[str] = []
    for b in blocks or []:
        t = b.get("type")
        if t == "paragraph":
            if b.get("text"):
                lines.append(b["text"])
        elif t == "table":
            cols = b.get("columns", [])
            for row in b.get("rows", []):
                head = str(row[0]) if row else ""
                rest = ", ".join(f"{c}: {v}" for c, v in zip(cols[1:], row[1:]))
                lines.append(f"{head} — {rest}" if head and rest else (head or rest))
        elif t == "card":
            for c in b.get("cards", []):
                head, items = c.get("heading", ""), c.get("items", [])
                lines.append(f"{head}: " + "; ".join(str(i) for i in items) if items else head)
        elif t == "checklist":
            lines.extend(f"- {it}" for it in b.get("items", []))
        elif t == "timeline":
            lines.extend(f"{e.get('label')}: {e.get('value')}" for e in b.get("events", []))
    text = "\n".join(x for x in lines if x and str(x).strip())
    if voice:
        text = re.sub(r"[*_#`>|]", "", text)
        text = re.sub(r"(?m)^\s*[-•]\s*", "", text)
        text = " ".join(text.split())
        if len(text) > 600:
            text = text[:600].rsplit(". ", 1)[0] + "."
    return text


DB_BLOCK_BUILDERS = {
    "price": price_block,
    "payment_plan": payment_plan_block,
    "inventory": inventory_block,
    "possession": possession_block,
    "builder": builder_block,
    "status": status_block,
    "offer": offer_block,
    "overview": overview_block,
    "location": location_block,
    "amenities": amenities_block,
}
