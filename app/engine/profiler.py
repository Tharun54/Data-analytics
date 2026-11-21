"""CSV profiling: type inference, column statistics and an auto-built dashboard report.

Pure standard library (single pass + sorted numeric copies), so a 10 MB upload profiles in
well under a second without pandas.
"""
from __future__ import annotations

import csv
import io
import json
import statistics
from collections import Counter
from datetime import datetime

from .schema import validate_report

DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")
MAX_CATEGORIES = 12


def _to_number(v: str) -> float | None:
    v = v.strip().replace(",", "").replace("$", "").replace("%", "")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _to_date(v: str) -> datetime | None:
    v = v.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def parse_csv(raw: bytes) -> tuple[list[str], list[dict]]:
    text = raw.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    columns = [c.strip() or f"column_{i}" for i, c in enumerate(reader.fieldnames)]
    rows = [{col: (row.get(orig) or "").strip() for col, orig in zip(columns, reader.fieldnames)} for row in reader]
    if not rows:
        raise ValueError("CSV has no data rows")
    return columns, rows


def profile(columns: list[str], rows: list[dict]) -> dict:
    out = {}
    for col in columns:
        values = [r[col] for r in rows if r[col] != ""]
        nulls = len(rows) - len(values)
        nums = [n for n in (_to_number(v) for v in values) if n is not None]
        dates = [d for d in (_to_date(v) for v in values[:500]) if d is not None]
        info: dict = {"nulls": nulls, "distinct": len(set(values))}
        if values and len(nums) / len(values) >= 0.9:
            info.update(type="numeric", min=min(nums), max=max(nums), mean=round(statistics.fmean(nums), 4),
                        median=statistics.median(nums), sum=round(sum(nums), 4),
                        stdev=round(statistics.stdev(nums), 4) if len(nums) > 1 else 0.0)
        elif values and len(dates) / min(len(values), 500) >= 0.9:
            info.update(type="date", min=min(dates).date().isoformat(), max=max(dates).date().isoformat())
        else:
            info.update(type="categorical", top=Counter(values).most_common(5))
        out[col] = info
    return out


def build_report(name: str, columns: list[str], rows: list[dict], prof: dict) -> dict:
    numeric = [c for c in columns if prof[c]["type"] == "numeric"]
    dates = [c for c in columns if prof[c]["type"] == "date"]
    cats = [c for c in columns if prof[c]["type"] == "categorical" and 1 < prof[c]["distinct"] <= 50]

    kpis = [{"label": "Rows", "value": len(rows), "unit": "", "change_pct": None, "note": name},
            {"label": "Columns", "value": len(columns), "unit": "", "change_pct": None, "note": f"{len(numeric)} numeric"}]
    for c in numeric[:4]:
        kpis.append({"label": f"Total {c}", "value": round(prof[c]["sum"], 2), "unit": "",
                     "change_pct": None, "note": f"mean {round(prof[c]['mean'], 2)}"})

    charts = []
    # Time series: first date column x first 3 numeric columns, aggregated per day/month.
    if dates and numeric:
        dcol = dates[0]
        buckets: dict[str, dict[str, float]] = {}
        span_days = (_to_date(prof[dcol]["max"]) - _to_date(prof[dcol]["min"])).days
        key_fmt = "%Y-%m" if span_days > 120 else "%Y-%m-%d"
        for r in rows:
            d = _to_date(r[dcol])
            if not d:
                continue
            k = d.strftime(key_fmt)
            b = buckets.setdefault(k, {})
            for n in numeric[:2]:
                b[n] = b.get(n, 0.0) + (_to_number(r[n]) or 0.0)
        labels = sorted(buckets)[-60:]
        # One chart per measure: measures of different scale never share an axis.
        for n in numeric[:2]:
            charts.append({"type": "line", "title": f"{n} over time", "labels": labels,
                           "series": [{"name": n, "data": [round(buckets[k].get(n, 0.0), 2) for k in labels]}],
                           "insight": f"Sum of '{n}' by {'month' if key_fmt == '%Y-%m' else 'day'} on '{dcol}'."})
    # Category breakdowns: sum of first numeric per category (or counts).
    for cat in cats[:2]:
        agg: Counter = Counter()
        for r in rows:
            agg[r[cat] or "(blank)"] += (_to_number(r[numeric[0]]) or 0.0) if numeric else 1
        top = agg.most_common(MAX_CATEGORIES)
        metric = f"sum of {numeric[0]}" if numeric else "count"
        charts.append({"type": "bar" if len(top) > 5 else "doughnut", "title": f"{metric} by {cat}",
                       "labels": [str(k) for k, _ in top], "series": [{"name": metric, "data": [round(v, 2) for _, v in top]}],
                       "insight": f"'{top[0][0]}' leads with {round(top[0][1] / (sum(agg.values()) or 1) * 100, 1)}% of the total."})
    # Distribution histogram of first numeric column.
    if numeric:
        n0 = numeric[0]
        vals = sorted(v for v in (_to_number(r[n0]) for r in rows) if v is not None)
        lo, hi = vals[0], vals[-1]
        bins = 10
        width = (hi - lo) / bins or 1
        counts = [0] * bins
        for v in vals:
            counts[min(int((v - lo) / width), bins - 1)] += 1
        charts.append({"type": "bar", "title": f"Distribution of {n0}",
                       "labels": [f"{round(lo + i * width, 2)}" for i in range(bins)],
                       "series": [{"name": "rows", "data": counts}],
                       "insight": f"Median {prof[n0]['median']}, σ {prof[n0]['stdev']}."})

    insights = []
    for c in columns:
        p = prof[c]
        if p["nulls"] / len(rows) > 0.2:
            insights.append({"headline": f"'{c}' is {round(p['nulls'] / len(rows) * 100)}% empty",
                             "detail": "Missing data may bias aggregates; consider imputing or excluding.", "impact": "medium"})
        if p["type"] == "numeric" and p["stdev"] and p["mean"] and p["stdev"] > 2 * abs(p["mean"]):
            insights.append({"headline": f"'{c}' is highly dispersed",
                             "detail": f"σ ({p['stdev']}) exceeds 2× the mean ({p['mean']}); check for outliers.", "impact": "medium"})
    if len(numeric) >= 2:
        a, b = numeric[0], numeric[1]
        pairs = [(x, y) for x, y in ((_to_number(r[a]), _to_number(r[b])) for r in rows) if x is not None and y is not None]
        if len(pairs) > 2:
            try:
                corr = statistics.correlation([p[0] for p in pairs], [p[1] for p in pairs])
                insights.append({"headline": f"Correlation {a} ↔ {b}: {corr:.2f}",
                                 "detail": ("Strong" if abs(corr) > 0.7 else "Weak-to-moderate") + " linear relationship.",
                                 "impact": "high" if abs(corr) > 0.7 else "low"})
            except statistics.StatisticsError:
                pass

    return validate_report({
        "title": f"Dataset analysis: {name}",
        "summary": f"{len(rows):,} rows × {len(columns)} columns ({len(numeric)} numeric, {len(dates)} date, "
                   f"{len(columns) - len(numeric) - len(dates)} categorical). Auto-generated profile and charts.",
        "kpis": kpis, "charts": charts, "insights": insights,
        "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        "recommendations": [], "sources": [], "confidence": "high",
    })


def compact_context(name: str, columns: list[str], rows: list[dict], prof: dict, sample_rows: int = 25) -> str:
    """A token-cheap description of the dataset for the AI engine (profile + small sample, not the raw file)."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns)
    w.writeheader()
    w.writerows(rows[:sample_rows])
    return f"Dataset '{name}', {len(rows)} rows.\nColumn profile (JSON):\n{json.dumps(prof, default=str)}\n\nFirst {sample_rows} rows:\n{buf.getvalue()}"
