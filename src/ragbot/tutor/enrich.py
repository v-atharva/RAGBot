"""Summary-driven query enrichment for course-wide mode.

The guardrail (held firm): summaries enrich and *frame*; they are never cited. Citations
always resolve to real transcript/material chunks. This module produces two artefacts, both
derived from the lecture summaries:

1. :func:`enrich_query` — expands the raw question with concept aliases + the highlight
   topics of the lectures where the concept is covered, so the hybrid retriever lands on the
   right transcript chunks. (Lexical expansion; never shown to the user, never cited.)
2. :func:`framing_context` — a compact "how this course frames the topic" block from the
   summaries, passed to the synthesis model for comprehension only — explicitly not citable.
"""

from __future__ import annotations

from ragbot.summaries.concepts import CONCEPT_ALIASES, ConceptEntry
from ragbot.summaries.models import LectureSummary


def _topics_for_location(summary: LectureSummary | None, timestamps: list[str]) -> list[str]:
    if not summary:
        return []
    by_ts = {h.timestamp: h.topic for h in summary.highlights}
    return [by_ts[ts] for ts in timestamps if ts in by_ts]


def enrich_query_with_terms(
    question: str,
    entries: list[ConceptEntry],
    summaries_by_prefix: dict[str, LectureSummary],
    *,
    max_terms: int = 12,
) -> tuple[str, list[str]]:
    """Like :func:`enrich_query`, but also returns the appended terms (for the Phase-2 trace,
    so the UI can highlight the query expansion)."""
    terms: list[str] = []
    for entry in entries:
        terms.extend(CONCEPT_ALIASES.get(entry.concept, []))
        for loc in entry.locations:
            terms.extend(
                _topics_for_location(summaries_by_prefix.get(loc.lecture_prefix), loc.timestamps)
            )

    seen: set[str] = set()
    picked: list[str] = []
    for term in terms:
        key = term.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        picked.append(term.strip())
        if len(picked) >= max_terms:
            break

    enriched = f"{question} {' '.join(picked)}".strip() if picked else question
    return enriched, picked


def enrich_query(
    question: str,
    entries: list[ConceptEntry],
    summaries_by_prefix: dict[str, LectureSummary],
    *,
    max_terms: int = 12,
) -> str:
    """Append concept aliases + summary highlight topics to the query for better retrieval."""
    return enrich_query_with_terms(
        question, entries, summaries_by_prefix, max_terms=max_terms
    )[0]


def framing_context(
    entries: list[ConceptEntry],
    summaries_by_prefix: dict[str, LectureSummary],
    *,
    max_lectures: int = 3,
    max_points: int = 6,
) -> str:
    """A short, summary-derived framing block (comprehension only — not citable)."""
    blocks: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        for loc in entry.locations:
            if loc.lecture_prefix in seen or not loc.timestamps:
                continue
            summary = summaries_by_prefix.get(loc.lecture_prefix)
            topics = _topics_for_location(summary, loc.timestamps)
            if not summary or not topics:
                continue
            seen.add(loc.lecture_prefix)
            lines = [f"  - {t}" for t in topics[:max_points]]
            blocks.append(f"Lecture {loc.lecture_prefix} — {summary.title}:\n" + "\n".join(lines))
            if len(blocks) >= max_lectures:
                return "\n\n".join(blocks)
    return "\n\n".join(blocks)
