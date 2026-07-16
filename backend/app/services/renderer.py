"""
Response Renderer (Constitution §16, §17).

Turns collected facts into render-ready blocks, choosing the easiest format:
Cards > Tables > Timeline > Checklist > Paragraph. The client just renders
what the engine returns. Never long paragraphs when data is structured.
"""
from __future__ import annotations

import re
from datetime import datetime


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


# --------------------------------------------------------------------------
# Humanised plain-text (for the website CHAT WIDGET / WhatsApp / voice only).
# The web app never uses this — it renders the structured blocks as tables.
# So this can be as conversational as we like WITHOUT ever running the facts
# through the LLM (numbers stay 100% accurate).
# --------------------------------------------------------------------------
def _group_inr(n: int) -> str:
    """Indian digit grouping: 200000 -> 2,00,000."""
    neg = n < 0
    s = str(abs(int(n)))
    if len(s) > 3:
        last3, rest, parts = s[-3:], s[:-3], []
        while len(rest) > 2:
            parts.insert(0, rest[-2:]); rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        s = ",".join(parts) + "," + last3
    return ("-" if neg else "") + s


def _n(v):
    """Clean number: drop trailing .0, group Indian-style. Non-numbers pass through."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        if float(v).is_integer():
            return _group_inr(int(v))
        frac = f"{round(v - int(v), 2):.2f}"[1:]
        return _group_inr(int(v)) + frac
    return str(v)


def _amt(v):
    """Money with lakh/crore for readability: 200000 -> ₹2 lakh, 12500000 -> ₹1.25 crore."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return str(v)
    n = float(v)
    if n >= 1e7:
        x = f"{n / 1e7:.2f}".rstrip("0").rstrip(".")
        return f"₹{x} crore"
    if n >= 1e5:
        x = f"{n / 1e5:.2f}".rstrip("0").rstrip(".")
        return f"₹{x} lakh"
    return "₹" + _n(v)


def _nice_date(v):
    """2027-12-31 -> Dec 2027 (leaves anything unparseable as-is)."""
    if not isinstance(v, str):
        return v
    try:
        return datetime.strptime(v[:10], "%Y-%m-%d").strftime("%b %Y")
    except (ValueError, TypeError):
        return v


_UNIT = {"per_sqft": "/sq ft", "total": " total"}


def _price_lines(cols, rows) -> list[str]:
    """Group a price table by configuration into one clean line each."""
    idx = {c: i for i, c in enumerate(cols)}
    ci, pi = idx.get("Configuration", 0), idx.get("Plan", 1)
    bi, si = idx.get("Base Price", 2), idx.get("Size", 3)
    ui, li, gi = idx.get("Unit", 4), idx.get("PLC", 5), idx.get("GST %", 6)
    groups: dict[str, list] = {}
    order: list[str] = []
    for r in rows:
        cfg = str(r[ci])
        if cfg not in groups:
            groups[cfg] = []; order.append(cfg)
        groups[cfg].append(r)
    out = []
    for cfg in order:
        rs = groups[cfg]
        size = rs[0][si] if si < len(rs[0]) else None
        plans = [f"{r[pi]} {_amt(r[bi])}{_UNIT.get(r[ui], '')}" for r in rs]
        extras = []
        if li < len(rs[0]) and rs[0][li]:
            extras.append(f"PLC {_amt(rs[0][li])}")
        if gi < len(rs[0]) and rs[0][gi]:
            extras.append(f"GST {_n(rs[0][gi])}%")
        line = f"**{cfg}**" + (f" ({_n(size)} sq ft)" if size else "") + ": " + ", ".join(plans)
        if extras:
            line += " · " + ", ".join(extras)
        out.append(line)
    return out


def blocks_to_text(blocks: list[dict], voice: bool = False) -> str:
    """Flatten answer blocks into a warm, concise plain-text answer for the
    website chat widget / WhatsApp / voice. Facts are formatted deterministically
    (Indian numbers, natural phrasing) — never sent through the LLM."""
    lines: list[str] = []
    for b in blocks or []:
        t = b.get("type")
        cols = b.get("columns", [])
        if t == "paragraph":
            if b.get("text"):
                lines.append(b["text"])  # LLM prose — leave as written
        elif t == "table" and "Base Price" in cols and "GST %" in cols:
            lines.extend(_price_lines(cols, b.get("rows", [])))  # price → grouped, clean
        elif t == "table" and cols[:1] == ["Configuration"] and "Available" in cols:
            for r in b.get("rows", []):
                lines.append(f"**{r[0]}**: {_n(r[2])} of {_n(r[1])} units available")
        elif t == "table":
            for row in b.get("rows", []):
                head = str(row[0]) if row else ""
                rest = ", ".join(f"{c}: {_n(v)}" for c, v in zip(cols[1:], row[1:]) if v not in (None, ""))
                lines.append(f"{head} — {rest}" if head and rest else (head or rest))
        elif t == "timeline":
            parts = [f"{e.get('label')}: {_nice_date(e.get('value'))}" for e in b.get("events", []) if e.get("value")]
            if parts:
                lines.append(" · ".join(parts))
        elif t == "card":
            for c in b.get("cards", []):
                head, items = c.get("heading", ""), c.get("items", [])
                items = [str(i) for i in items if i not in (None, "")]
                lines.append((f"**{head}** — " + ", ".join(items)) if items else head)
        elif t == "checklist":
            lines.extend(f"• {it}" for it in b.get("items", []))
    text = "\n".join(x for x in lines if x and str(x).strip())
    if voice:
        text = re.sub(r"[*_#`>|•·]", "", text)
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
