"""
Helpers for answering a narrow set of simple live-data questions deterministically.

This module is intentionally conservative. It only covers a small class of
objective questions:
- most fresh / new snow right now
- deepest base / base depth right now

Anything else should fall back to the main agent flow.
"""

from __future__ import annotations

import re
from typing import Any, Callable


PASS_NAMES = ("IKON", "EPIC", "INDY")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _effective_passes(question: str, selected_passes: list[str]) -> list[str]:
    """
    Determine which pass filter should apply.

    Priority:
    1. If the question explicitly mentions IKON / EPIC / INDY, use that.
    2. Otherwise use the UI / API selected_passes.
    """
    q = question.upper()
    mentioned = [p for p in PASS_NAMES if p in q]
    if mentioned:
        return mentioned
    if not selected_passes:
        return ["All"]
    return selected_passes


def _detect_metric(question: str) -> str | None:
    q = _normalize(question)

    blockers = [
        "historical", "history", "average", "season", "january", "february",
        "march", "april", "forecast", "weekend", "this weekend", "recommend",
        "should i ski", "where should i ski", "avoid i-70", "trip", "itinerary",
        "compare", "consistent", "usually", "typically",
    ]
    if any(token in q for token in blockers):
        return None

    fresh_terms = [
        "fresh snow", "new snow", "most snow right now", "snowiest right now",
        "most powder right now", "freshest snow", "highest 72h",
    ]
    base_terms = [
        "deepest base", "most base", "base depth", "deepest snowpack",
        "biggest base", "highest base",
    ]

    if any(token in q for token in fresh_terms):
        return "new_snow_72h"
    if any(token in q for token in base_terms):
        return "snow_depth_in"

    return None


def _sort_key(metric: str, data: dict[str, Any]) -> tuple[float, float]:
    primary = float(data.get(metric, 0) or 0)
    secondary_metric = "snow_depth_in" if metric == "new_snow_72h" else "new_snow_72h"
    secondary = float(data.get(secondary_metric, 0) or 0)
    return (primary, secondary)


def _format_top_line(
    resort: str,
    metric: str,
    data: dict[str, Any],
    selected_passes: list[str],
) -> str:
    value = float(data.get(metric, 0) or 0)

    pass_phrase = ""
    if selected_passes and "All" not in selected_passes:
        pass_phrase = f" among {', '.join(selected_passes)} resorts"

    if metric == "new_snow_72h":
        if value <= 0:
            return f"Based on live SNOTEL data, no resort{pass_phrase} is reporting any new snow in the last 72 hours right now."
        return (
            f"Based on live SNOTEL data, {resort} currently has the most new snow{pass_phrase} "
            f"at {value:.0f} inches in the last 72 hours."
        )

    return (
        f"Based on live SNOTEL data, {resort} currently has the deepest base{pass_phrase} "
        f"at {value:.0f} inches."
    )


def _format_followups(ranked: list[tuple[str, dict[str, Any]]], metric: str) -> str:
    if len(ranked) <= 1:
        return ""

    pieces = []
    for resort, data in ranked[1:3]:
        value = float(data.get(metric, 0) or 0)
        pieces.append(f'{resort} ({value:.0f}")')

    if not pieces:
        return ""

    if len(pieces) == 1:
        return f" Next is {pieces[0]}."
    return f" Next are {pieces[0]} and {pieces[1]}."


def try_answer_simple_live_question(
    question: str,
    conditions: dict[str, Any],
    selected_passes: list[str],
    resort_stations: dict[str, dict[str, Any]],
    pass_filter_fn: Callable[[str, list[str]], bool],
) -> dict[str, Any] | None:
    """
    Return a deterministic answer for a narrow class of simple live-data questions.

    Output format:
        {
            "answer": "...",
            "ranking": [...]
        }

    Returns None if the question should fall back to the LLM agent.
    """
    metric = _detect_metric(question)
    if metric is None:
        return None

    effective_passes = _effective_passes(question, selected_passes)

    valid: list[tuple[str, dict[str, Any]]] = []
    for resort in resort_stations:
        if not pass_filter_fn(resort, effective_passes):
            continue
        data = conditions.get(resort)
        if data is None:
            continue
        valid.append((resort, data))

    if not valid:
        pass_phrase = ""
        if effective_passes and "All" not in effective_passes:
            pass_phrase = f" for {', '.join(effective_passes)} resorts"
        return {
            "answer": f"I couldn't find any live SNOTEL data{pass_phrase} right now.",
            "ranking": [],
        }

    ranked = sorted(
        valid,
        key=lambda item: (_sort_key(metric, item[1]), item[0]),
        reverse=True,
    )

    top_resort, top_data = ranked[0]
    answer = _format_top_line(top_resort, metric, top_data, effective_passes)
    answer += _format_followups(ranked, metric)

    ranking = [resort for resort, _ in ranked]
    return {
        "answer": answer,
        "ranking": ranking,
    }
