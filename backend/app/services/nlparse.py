"""
Small deterministic parsers for budget and configuration extracted from a query.
Deterministic-first (Golden Rule): we parse numbers with regex, not the LLM.
"""
from __future__ import annotations

import re

_CONFIG_RE = re.compile(r"\b([1-5])\s*bhk\b", re.I)


def parse_config(query: str) -> str | None:
    m = _CONFIG_RE.search(query)
    if m:
        return f"{m.group(1)}BHK"
    q = query.lower()
    if "villa" in q:
        return "Villa"
    if "plot" in q:
        return "Plot"
    return None


def parse_budget(query: str) -> float | None:
    """Return a budget in rupees, understanding cr/crore and lakh/lac."""
    q = query.lower()
    # e.g. "2 cr", "1.5 crore", "80 lakh", "under 2cr"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(cr|crore|lakh|lac|l)\b", q)
    if m:
        val = float(m.group(1))
        unit = m.group(2)
        if unit in ("cr", "crore"):
            return val * 1_00_00_000
        return val * 1_00_000  # lakh/lac/l
    # bare large number, e.g. "under 20000000"
    m2 = re.search(r"\b(\d{6,})\b", q)
    if m2:
        return float(m2.group(1))
    return None
