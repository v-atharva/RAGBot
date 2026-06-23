"""Tutor orchestration: route a question + mode to a grounded, structured answer.

Shared prelude: match course concepts in the question, then build the authoritative,
deterministic reference list from the concept index.

- lecture_only -> "when / where" locator. No retrieval, no explanation. The model only
  phrases the locator answer over the pre-computed references (and even if it misbehaves,
  the structured references are what the UI renders).
- course_wide -> summary-enriched retrieval over transcripts/materials, then explain +
  ground with citations, then append the same reference list framed as further reading.
"""

from __future__ import annotations

from ragbot.config import Settings
from ragbot.retrieve.index import HybridIndex
from ragbot.summaries.concepts import ConceptEntry

from .concept_store import ConceptStore
from .enrich import enrich_query, framing_context
from .llm import LLMClient, LLMError
from .prompts import (
    COURSE_WIDE_SYSTEM,
    LECTURE_ONLY_SYSTEM,
    build_course_wide_user,
    build_lecture_only_user,
)
from .references import build_reference_list
from .schemas import LectureReference, Mode, QueryRequest, QueryResponse
from .segment import segment_prose

_NO_MATCH = (
    "I couldn't find that topic in this course's materials. Try a core database topic — "
    "for example normalization, BCNF, joins, primary/foreign keys, or transactions."
)


def answer(
    request: QueryRequest,
    *,
    store: ConceptStore,
    index: HybridIndex,
    llm: LLMClient,
    settings: Settings,
) -> QueryResponse:
    entries = store.match(request.question)
    if not entries:
        return QueryResponse(
            mode=request.mode,
            question=request.question,
            no_concept_match=True,
            intro_text=_NO_MATCH,
        )

    primary = entries[0]
    references = build_reference_list(primary, store.summaries_by_prefix)
    matched = [e.concept for e in entries]

    if request.mode is Mode.lecture_only:
        return _lecture_only(request, references, matched, llm)
    return _course_wide(request, entries, references, matched, store, index, llm, settings)


def _lecture_only(
    request: QueryRequest,
    references: list[LectureReference],
    matched: list[str],
    llm: LLMClient,
) -> QueryResponse:
    """A 'when / where' locator: the model phrases the answer over the authoritative,
    pre-computed reference list (it is told to locate, never to explain).

    The structured ``references`` are what the UI renders as chips, so even if the model
    drifts, the cited data stays correct. If the model is unavailable we fall back to a
    deterministic locator so the mode still works offline.
    """
    user = build_lecture_only_user(request.question, references)
    try:
        prose = llm.chat(LECTURE_ONLY_SYSTEM, user, temperature=0.2)
        if not prose.strip():
            prose = _deterministic_locator(references)
    except LLMError:
        prose = _deterministic_locator(references)

    return QueryResponse(
        mode=request.mode,
        question=request.question,
        matched_concepts=matched,
        intro_text=f"Here's where “{matched[0]}” is covered in the lectures.",
        explanation_segments=segment_prose(prose, references),
        references=references,
        references_caption="Chronological timeline — open the recording at any timestamp.",
    )


def _course_wide(
    request: QueryRequest,
    entries: list[ConceptEntry],
    references: list[LectureReference],
    matched: list[str],
    store: ConceptStore,
    index: HybridIndex,
    llm: LLMClient,
    settings: Settings,
) -> QueryResponse:
    enriched = enrich_query(request.question, entries, store.summaries_by_prefix)
    try:
        chunks = index.search(
            enriched, k=settings.retrieval_k, exclude_high_sensitivity=True
        )
    except RuntimeError:
        # Index not built yet — explain without grounding rather than failing the request.
        chunks = []
    framing = framing_context(entries, store.summaries_by_prefix)

    user = build_course_wide_user(request.question, framing, chunks)
    try:
        prose = llm.chat(COURSE_WIDE_SYSTEM, user, temperature=0.2)
    except LLMError as exc:
        prose = f"(The language model is currently unavailable: {exc})"

    return QueryResponse(
        mode=request.mode,
        question=request.question,
        matched_concepts=matched,
        explanation_segments=segment_prose(prose, references),
        references=references,
        references_caption=(
            "These are the lecture references behind this answer — review them to "
            "strengthen your understanding."
        ),
        citations=[c.citation for c in chunks],
    )


def _deterministic_locator(references: list[LectureReference]) -> str:
    """Fallback locator text if the model is unavailable — keeps lecture-only useful offline."""
    lines: list[str] = []
    first = next((r for r in references if r.is_first_mention), None)
    if first and first.timestamps:
        lines.append(
            f"First covered in [Lecture {first.lecture_number} @ {first.timestamps[0].timestamp}]."
        )
    for ref in references:
        for ts in ref.timestamps:
            if first and ref is first and ts is first.timestamps[0]:
                continue
            blurb = f" — {ts.blurb}" if ts.blurb else ""
            lines.append(f"- [Lecture {ref.lecture_number} @ {ts.timestamp}]{blurb}")
    lines.append("Watch the recordings at these timestamps to hear it explained.")
    return "\n".join(lines)
