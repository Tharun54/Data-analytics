"""Claude-powered research engine.

One request does the whole job: Claude researches the topic with the server-side
web search tool, reasons about it (adaptive thinking), and returns a report that is
constrained to ANALYSIS_SCHEMA via structured outputs, so it renders straight into a dashboard.
"""
from __future__ import annotations

import json
import logging

import anthropic

from ..config import settings
from .schema import ANALYSIS_SCHEMA, validate_report

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the senior analyst at CSE Plus, a data analytics firm. Clients give you a topic \
(a market, company, technology, policy, trend, product, region — anything) and you deliver a \
dashboard-ready analysis.

How to work:
- Research the topic with web search when it is available; prefer primary and recent sources \
(official statistics, filings, reputable research firms, major outlets). Cite what you use in `sources`.
- Every number must be real or a clearly labelled estimate. Put the period and basis in the KPI `note` \
(e.g. "2025, global, Statista est."). If you cannot find a figure, choose a different KPI rather than invent one.
- Charts must be internally consistent: every series has exactly one value per label. Use line/area for \
time series, bar for comparisons, pie/doughnut for shares that sum to ~100.
- Insights are "so what" statements a decision-maker can act on, not restatements of the charts.
- Set `confidence` honestly: high = mostly primary sources; low = sparse or conflicting data.
- Write for a busy executive: plain language, no filler."""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key or None, max_retries=3)


def _final_text(message) -> str:
    """With web search the response interleaves text and tool blocks; the structured JSON is the
    text emitted after the last tool result."""
    blocks = list(message.content)
    last_tool = max((i for i, b in enumerate(blocks) if b.type.endswith("tool_result")), default=-1)
    return "".join(b.text for b in blocks[last_tool + 1:] if b.type == "text")


def run_topic_analysis(topic: str, *, web_research: bool, context: str | None = None) -> dict:
    user_content = f"Topic: {topic}"
    if context:
        user_content += f"\n\nClient-supplied context / data:\n{context}"

    tools = []
    if web_research and settings.web_search:
        tools.append({"type": "web_search_20260209", "name": "web_search", "max_uses": 8})

    messages: list = [{"role": "user", "content": user_content}]
    for _ in range(4):  # resume on pause_turn (long server-tool turns)
        with _client().beta.messages.stream(
            model=settings.model,
            max_tokens=64000,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=tools or anthropic.omit,
            thinking={"type": "adaptive"},
            output_config={"effort": settings.effort,
                           "format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA}},
            # On a safety-classifier decline, the API re-runs the request on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()

        if message.stop_reason == "pause_turn":
            messages = [messages[0], {"role": "assistant", "content": message.content}]
            continue
        if message.stop_reason == "refusal":
            raise RuntimeError("The model declined to analyse this topic.")
        if message.stop_reason == "max_tokens":
            raise RuntimeError("Analysis was cut off (max_tokens). Try a narrower topic.")
        break
    else:
        raise RuntimeError("Research did not finish in time; try a narrower topic.")

    log.info("analysis usage: %s", message.usage)
    text = _final_text(message)
    try:
        return validate_report(json.loads(text))
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Model returned an invalid report: {exc}") from exc


def friendly_error(exc: Exception) -> str:
    """Map SDK errors (most specific first) to messages safe to show customers."""
    if isinstance(exc, anthropic.AuthenticationError):
        return "AI engine is misconfigured (invalid API key). Contact support."
    if isinstance(exc, anthropic.RateLimitError):
        return "AI engine is busy (rate limited). Please retry in a minute."
    if isinstance(exc, anthropic.BadRequestError):
        return f"AI engine rejected the request: {exc.message}"
    if isinstance(exc, anthropic.APIStatusError):
        return f"AI engine error ({exc.status_code}). Please retry."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Could not reach the AI engine. Please retry."
    return str(exc)
