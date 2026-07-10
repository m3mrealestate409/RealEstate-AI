"""
Response Renderer (Constitution §16, §17).

Turns collected facts into render-ready blocks, choosing the easiest format:
Cards > Tables > Timeline > Checklist > Paragraph. The client just renders
what the engine returns. Never long paragraphs when data is structured.
"""
from __future__ import annotations


def price_block(project_name: str, data: dict) -> dict:
    return {
        "type": "table",
        "title": f"{project_name} - Price",
        "columns": ["Configuration", "Carpet Area", "Base Price", "Unit", "PLC", "GST %"],
        "rows": [
            [
                r["configuration"],
                r.get("carpet_area"),
                r["base_price"],
                r["price_unit"],
                r.get("plc"),
                r.get("gst_percent"),
            ]
            for r in data.get("prices", [])
        ],
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
        "title": f"{project_name} - Builder",
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


def rag_block(title: str, chunks: list) -> dict:
    return {
        "type": "checklist",
        "title": title,
        "items": [c.content for c in chunks],
    }


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


DB_BLOCK_BUILDERS = {
    "price": price_block,
    "payment_plan": payment_plan_block,
    "inventory": inventory_block,
    "possession": possession_block,
    "builder": builder_block,
    "status": status_block,
    "offer": offer_block,
    "overview": overview_block,
}
