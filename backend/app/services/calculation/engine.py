"""
Calculation Engine — pure, deterministic, unit-testable functions.

Constitution §18: AI must NEVER calculate with language reasoning. Every
percentage / cost / EMI / ROI is computed here. The LLM may only *explain*
these numbers, never produce them.

Each calculator returns an itemised, render-ready dict.
"""
from __future__ import annotations


def _round(x: float, n: int = 2) -> float:
    return round(float(x), n)


def total_cost(
    *,
    base_price: float,
    area: float,
    price_unit: str = "per_sqft",
    plc: float = 0.0,
    other_charges: float = 0.0,
    gst_percent: float = 0.0,
) -> dict:
    """Itemised total cost of a unit."""
    base = base_price * area if price_unit == "per_sqft" else base_price
    subtotal = base + (plc or 0.0) + (other_charges or 0.0)
    gst_amount = subtotal * (gst_percent or 0.0) / 100.0
    total = subtotal + gst_amount
    return {
        "line_items": [
            {"label": "Base amount", "amount": _round(base)},
            {"label": "PLC", "amount": _round(plc or 0.0)},
            {"label": "Other charges", "amount": _round(other_charges or 0.0)},
            {"label": f"GST ({gst_percent or 0}%)", "amount": _round(gst_amount)},
        ],
        "subtotal": _round(subtotal),
        "gst_amount": _round(gst_amount),
        "total": _round(total),
    }


def payment_schedule(*, total_amount: float, milestones: list[dict]) -> dict:
    """Split a total across payment-plan milestones (each {label, percent})."""
    rows = []
    running = 0.0
    for m in milestones:
        amt = total_amount * float(m["percent"]) / 100.0
        running += amt
        rows.append(
            {
                "label": m["label"],
                "percent": _round(m["percent"]),
                "amount": _round(amt),
                "cumulative": _round(running),
            }
        )
    return {"total_amount": _round(total_amount), "schedule": rows}


def gst(*, taxable_value: float, rate: float) -> dict:
    amt = taxable_value * rate / 100.0
    return {"taxable_value": _round(taxable_value), "rate": rate, "gst_amount": _round(amt)}


def plc(*, base: float, premium_percent: float) -> dict:
    amt = base * premium_percent / 100.0
    return {"base": _round(base), "premium_percent": premium_percent, "plc": _round(amt)}


def emi(*, principal: float, annual_rate: float, tenure_months: int) -> dict:
    """Standard reducing-balance EMI."""
    r = annual_rate / 12.0 / 100.0
    n = tenure_months
    if r == 0:
        monthly = principal / n
    else:
        monthly = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
    total_payable = monthly * n
    return {
        "principal": _round(principal),
        "annual_rate": annual_rate,
        "tenure_months": n,
        "emi": _round(monthly),
        "total_payable": _round(total_payable),
        "total_interest": _round(total_payable - principal),
    }


def roi(*, investment: float, current_value: float, years: float | None = None) -> dict:
    gain = current_value - investment
    pct = (gain / investment * 100.0) if investment else 0.0
    out = {
        "investment": _round(investment),
        "current_value": _round(current_value),
        "gain": _round(gain),
        "roi_percent": _round(pct),
    }
    if years and years > 0 and investment > 0:
        cagr = ((current_value / investment) ** (1 / years) - 1) * 100.0
        out["cagr_percent"] = _round(cagr)
    return out


def rental_yield(*, annual_rent: float, property_value: float) -> dict:
    y = (annual_rent / property_value * 100.0) if property_value else 0.0
    return {
        "annual_rent": _round(annual_rent),
        "property_value": _round(property_value),
        "rental_yield_percent": _round(y),
    }


def stamp_duty(*, property_value: float, rate: float) -> dict:
    amt = property_value * rate / 100.0
    return {"property_value": _round(property_value), "rate": rate, "stamp_duty": _round(amt)}


# Registry used by the /calculate/{type} endpoint and the orchestrator.
CALCULATORS = {
    "total_cost": total_cost,
    "payment_schedule": payment_schedule,
    "gst": gst,
    "plc": plc,
    "emi": emi,
    "roi": roi,
    "rental_yield": rental_yield,
    "stamp_duty": stamp_duty,
}


def run_calculation(calc_type: str, params: dict) -> dict:
    if calc_type not in CALCULATORS:
        raise ValueError(f"Unknown calculation type: {calc_type}")
    return CALCULATORS[calc_type](**params)
