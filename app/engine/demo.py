"""Offline demo engine: deterministic, topic-seeded synthetic report.

Used when no ANTHROPIC_API_KEY is configured, so the product (and tests) run end-to-end
with zero external dependencies. Every figure is labelled as illustrative.
"""
from __future__ import annotations

import hashlib
import random

from .schema import validate_report


def run_demo_analysis(topic: str) -> dict:
    seed = int(hashlib.sha256(topic.lower().encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    t = topic.strip().rstrip(".") or "Topic"

    years = [str(y) for y in range(2020, 2027)]
    base = rng.uniform(5, 80)
    growth = rng.uniform(0.04, 0.22)
    size = [round(base * (1 + growth) ** i * rng.uniform(0.96, 1.04), 1) for i in range(len(years))]

    segments = ["Enterprise", "SMB", "Consumer", "Public sector"]
    shares = [rng.uniform(10, 40) for _ in segments]
    total = sum(shares)
    shares = [round(s / total * 100, 1) for s in shares]

    regions = ["North America", "Europe", "Asia-Pacific", "LATAM", "MEA"]
    region_vals = [round(rng.uniform(2, 30), 1) for _ in regions]

    quarters = ["Q1", "Q2", "Q3", "Q4"]
    interest = [round(rng.uniform(40, 100)) for _ in quarters]
    sentiment = [round(rng.uniform(30, 90)) for _ in quarters]

    cagr = round(((size[-1] / size[0]) ** (1 / (len(size) - 1)) - 1) * 100, 1)
    report = {
        "title": f"{t}: Market & Trend Analysis",
        "summary": (
            f"{t} shows an estimated compound annual growth of {cagr}% between 2020 and 2026, "
            f"reaching roughly {size[-1]} (index units) this year. {segments[shares.index(max(shares))]} is the "
            f"largest segment at {max(shares)}% share, and {regions[region_vals.index(max(region_vals))]} leads "
            "regionally. DEMO MODE: figures are illustrative — connect the AI engine for sourced research."
        ),
        "kpis": [
            {"label": "Market size (2026)", "value": size[-1], "unit": "index", "change_pct": round((size[-1] / size[-2] - 1) * 100, 1), "note": "illustrative"},
            {"label": "CAGR 2020–26", "value": cagr, "unit": "%", "change_pct": None, "note": "illustrative"},
            {"label": "Top segment share", "value": max(shares), "unit": "%", "change_pct": round(rng.uniform(-3, 5), 1), "note": segments[shares.index(max(shares))]},
            {"label": "Search interest", "value": interest[-1], "unit": "/100", "change_pct": round((interest[-1] / interest[0] - 1) * 100, 1), "note": "Q4 vs Q1"},
            {"label": "Net sentiment", "value": sentiment[-1], "unit": "/100", "change_pct": round((sentiment[-1] / sentiment[0] - 1) * 100, 1), "note": "Q4 vs Q1"},
        ],
        "charts": [
            {"type": "line", "title": "Market size over time", "labels": years,
             "series": [{"name": t, "data": size}], "insight": f"Steady expansion at ~{cagr}% CAGR."},
            {"type": "doughnut", "title": "Share by segment", "labels": segments,
             "series": [{"name": "Share %", "data": shares}], "insight": f"{segments[shares.index(max(shares))]} dominates demand."},
            {"type": "bar", "title": "Size by region", "labels": regions,
             "series": [{"name": "Index", "data": region_vals}], "insight": f"{regions[region_vals.index(max(region_vals))]} is the largest region."},
            {"type": "area", "title": "Interest vs sentiment", "labels": quarters,
             "series": [{"name": "Interest", "data": interest}, {"name": "Sentiment", "data": sentiment}],
             "insight": "Attention and sentiment move together; watch for divergence."},
        ],
        "insights": [
            {"headline": "Growth is structural, not cyclical", "detail": f"Consistent year-on-year gains suggest durable demand for {t}.", "impact": "high"},
            {"headline": "Segment concentration risk", "detail": "Over-reliance on one segment exposes revenue to a single buyer type.", "impact": "medium"},
            {"headline": "Regional white space", "detail": f"{regions[region_vals.index(min(region_vals))]} is under-penetrated relative to its population.", "impact": "medium"},
        ],
        "swot": {
            "strengths": ["Established demand", "Clear growth trajectory"],
            "weaknesses": ["Segment concentration", "Data transparency varies by region"],
            "opportunities": ["Expansion into under-served regions", "Product bundling for SMB"],
            "threats": ["New entrants compressing margins", "Regulatory change"],
        },
        "recommendations": [
            f"Prioritise the {segments[shares.index(max(shares))]} segment while piloting a second segment.",
            f"Test market entry in {regions[region_vals.index(min(region_vals))]}.",
            "Track sentiment monthly as a leading indicator of demand.",
        ],
        "sources": [],
        "confidence": "low",
    }
    return validate_report(report)
