"""The analysis report contract. Every engine (AI, demo, CSV profiler) returns this shape,
so the dashboard renderer only has to understand one format."""

ANALYSIS_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "summary", "kpis", "charts", "insights", "swot",
                 "recommendations", "sources", "confidence"],
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string", "description": "3-5 sentence executive summary"},
        "kpis": {
            "type": "array",
            "description": "4-6 headline metrics",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["label", "value", "unit", "change_pct", "note"],
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "number"},
                    "unit": {"type": "string", "description": "e.g. 'USD bn', '%', 'users m', '' if unitless"},
                    "change_pct": {"anyOf": [{"type": "number"}, {"type": "null"}], "description": "YoY or period change in percent, null if unknown"},
                    "note": {"type": "string", "description": "period / basis of the figure"},
                },
            },
        },
        "charts": {
            "type": "array",
            "description": "3-5 charts",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["type", "title", "labels", "series", "insight"],
                "properties": {
                    "type": {"type": "string", "enum": ["line", "bar", "pie", "doughnut", "area"]},
                    "title": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "series": {
                        "type": "array",
                        "items": {
                            "type": "object", "additionalProperties": False,
                            "required": ["name", "data"],
                            "properties": {
                                "name": {"type": "string"},
                                "data": {"type": "array", "items": {"type": "number"}},
                            },
                        },
                    },
                    "insight": {"type": "string", "description": "one-line takeaway"},
                },
            },
        },
        "insights": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["headline", "detail", "impact"],
                "properties": {
                    "headline": {"type": "string"},
                    "detail": {"type": "string"},
                    "impact": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "swot": {
            "type": "object", "additionalProperties": False,
            "required": ["strengths", "weaknesses", "opportunities", "threats"],
            "properties": {k: {"type": "array", "items": {"type": "string"}}
                           for k in ["strengths", "weaknesses", "opportunities", "threats"]},
        },
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "sources": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["title", "url"],
                "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
            },
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"],
                       "description": "how well-sourced the numbers are"},
    },
}


def validate_report(report: dict) -> dict:
    """Light structural check + normalisation so the UI never crashes on a bad chart."""
    for key in ANALYSIS_SCHEMA["required"]:
        if key not in report:
            raise ValueError(f"report missing '{key}'")
    clean_charts = []
    for chart in report["charts"]:
        n = len(chart.get("labels", []))
        series = [s for s in chart.get("series", []) if n and len(s.get("data", [])) == n]
        if series:
            clean_charts.append({**chart, "series": series})
    report["charts"] = clean_charts
    return report
