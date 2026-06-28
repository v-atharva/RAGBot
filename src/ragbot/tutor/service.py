"""Tutor orchestration: route a question + mode to a grounded, structured answer.

Pipeline (per workstreams A, C2/C3, E):
- Condense a conversational follow-up into a standalone question (E) — no-op without history.
- Match curated concepts (KAG-lite) — an *optional booster*, never a gate (A).
- lecture_only -> a "when/where" locator. Driven by the concept timeline when a concept
  matches, otherwise by retrieved transcript chunks (A.3). No teaching.
- course_wide -> summary-enriched retrieval, then synthesis that grounds claims with numbered
  [S#] source markers (C2). The reference list is the evidence actually cited (C3); the concept
  timeline is demoted to a secondary "where else this appears" block.
- The "no match" nudge fires only when retrieval ALSO comes back empty (A.1).
"""

from __future__ import annotations

import os

from ragbot.config import Settings
from ragbot.ingest.models import Category
from ragbot.retrieve.index import HybridIndex, RetrievalTrace, RetrievedChunk
from ragbot.summaries.concepts import ConceptEntry
from ragbot.summaries.lecture_meta import LectureMeta, format_date, load_lecture_meta
from ragbot.summaries.models import LectureSummary

from .citations import (
    CitationRef,
    build_marker_map,
    citation_for_chunk,
    to_marker_payload,
)
from .concept_store import ConceptStore
from .enrich import enrich_query_with_terms, framing_context
from .followup import condense_followup
from .llm import LLMClient, LLMError
from .prompts import (
    COURSE_WIDE_SYSTEM,
    LECTURE_ONLY_SYSTEM,
    build_course_wide_user,
    build_lecture_only_user,
)
from .references import build_reference_list, recording_label
from .schemas import (
    CitedRetrieved,
    ConceptTrace,
    ExcludedChunk,
    LectureReference,
    LexicalGate,
    Mode,
    PipelineTrace,
    QueryRequest,
    QueryResponse,
    RankedChunk,
    TimestampRef,
    TracedChunk,
)
from .segment import extract_used_markers

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
    meta = load_lecture_meta()

    # STEP 1 — Condense a follow-up into a standalone question (no-op without history). The
    # original phrasing is preserved for display; the condensed form drives retrieval/synthesis.
    history = request.history[-settings.max_history_turns :]
    condensed = condense_followup(request.question, history, llm)

    # STEP 2 — Concept match (KAG-lite). Optional booster: we do NOT bail when empty (A.1).
    entries = store.match(condensed)

    # STEP 3 — Route by mode.
    if request.mode is Mode.lecture_only:
        return _lecture_only(request, condensed, entries, store, index, llm, settings, meta)
    return _course_wide(request, condensed, entries, store, index, llm, settings, meta)


def _no_match(request: QueryRequest) -> QueryResponse:
    return QueryResponse(
        mode=request.mode,
        question=request.question,
        no_concept_match=True,
        intro_text=_NO_MATCH,
    )


def _course_wide(
    request: QueryRequest,
    condensed: str,
    entries: list[ConceptEntry],
    store: ConceptStore,
    index: HybridIndex,
    llm: LLMClient,
    settings: Settings,
    meta: dict[str, LectureMeta],
) -> QueryResponse:
    # 3a. Enrich with concept aliases/topics when a concept matched; else retrieve on the raw text.
    enriched, appended_terms = (
        enrich_query_with_terms(condensed, entries, store.summaries_by_prefix)
        if entries
        else (condensed, [])
    )
    rtrace: RetrievalTrace | None = None
    try:
        # 3b. Hybrid retrieval (dense + BM25 + RRF). Solution-key/exam-review chunks are included
        # unless the (default-off) assignment guardrail is enabled via settings.block_solution_keys.
        if request.with_trace:
            chunks, rtrace = index.search_with_trace(
                enriched,
                k=settings.retrieval_k,
                exclude_high_sensitivity=settings.block_solution_keys,
            )
        else:
            chunks = index.search(
                enriched,
                k=settings.retrieval_k,
                exclude_high_sensitivity=settings.block_solution_keys,
            )
    except RuntimeError:
        # Index not built yet — explain without grounding rather than failing the request.
        chunks = []

    # A.2: show the "nothing found" nudge when there is no concept AND no genuine evidence —
    # either nothing retrieved, or the query shares no content vocabulary with the course
    # (dense retrieval always returns neighbours, so a lexical gate rejects off-topic queries).
    if not entries and (not chunks or not index.has_lexical_match(condensed)):
        return _no_match(request)

    # 3c. Summary framing (comprehension only, never cited). Numbered markers for each chunk.
    framing = framing_context(entries, store.summaries_by_prefix) if entries else ""
    marker_map = build_marker_map(chunks, meta, store.summaries_by_prefix)

    # 3d. Synthesis: one cohesive, self-contained lesson grounded via [S#] markers (C2/C4).
    history = request.history[-settings.max_history_turns :]
    user = build_course_wide_user(condensed, framing, chunks, marker_map, history=history)
    try:
        prose = llm.chat(COURSE_WIDE_SYSTEM, user, temperature=settings.course_wide_temperature)
    except LLMError as exc:
        prose = f"(The language model is currently unavailable: {exc})"

    # 3e. Resolve which [S#] markers the model used; cited sources become the reference list.
    # The markdown itself is returned verbatim — the frontend renders it and swaps [S#] for chips.
    used, marker_ids = extract_used_markers(prose, marker_map)
    references = _evidence_references(used, store.summaries_by_prefix)

    # Concept timeline is demoted to a secondary "where else this appears" block (C3).
    coverage = (
        build_reference_list(entries[0], store.summaries_by_prefix) if entries else []
    )

    trace = (
        _assemble_trace(
            request=request,
            condensed=condensed,
            entries=entries,
            enriched=enriched,
            appended_terms=appended_terms,
            index=index,
            rtrace=rtrace,
            chunks=chunks,
            marker_map=marker_map,
            marker_ids=marker_ids,
            used=used,
            framing=framing,
            prose=prose,
            settings=settings,
        )
        if request.with_trace
        else None
    )

    return QueryResponse(
        mode=request.mode,
        question=request.question,
        matched_concepts=[e.concept for e in entries],
        answer_markdown=prose,
        marker_map=to_marker_payload(marker_map),
        references=references,
        references_caption="Sources for this answer." if references else "",
        coverage_timeline=coverage,
        coverage_caption="Where else this appears in the course." if coverage else "",
        citations=[r.display for r in used],
        trace=trace,
    )


def _lecture_only(
    request: QueryRequest,
    condensed: str,
    entries: list[ConceptEntry],
    store: ConceptStore,
    index: HybridIndex,
    llm: LLMClient,
    settings: Settings,
    meta: dict[str, LectureMeta],
) -> QueryResponse:
    """A 'when / where' locator. Concept-driven when a concept matched; otherwise retrieval-backed.

    The structured ``references`` are what the UI renders, so even if the model drifts the
    cited data stays correct. With the LLM down we fall back to a deterministic locator.
    """
    chunks: list[RetrievedChunk] = []
    rtrace: RetrievalTrace | None = None
    if entries:
        references = build_reference_list(entries[0], store.summaries_by_prefix)
        matched = [e.concept for e in entries]
        intro = f"Here's where “{matched[0]}” is covered in the lectures."
    elif not index.has_lexical_match(condensed):
        # A.3: no concept and no shared course vocabulary -> genuinely off-topic.
        return _no_match(request)
    else:
        # A.3: no concept — retrieve transcript chunks and build the locator from them.
        try:
            if request.with_trace:
                chunks, rtrace = index.search_with_trace(
                    condensed,
                    k=settings.retrieval_k,
                    exclude_high_sensitivity=settings.block_solution_keys,
                )
            else:
                chunks = index.search(
                    condensed,
                    k=settings.retrieval_k,
                    exclude_high_sensitivity=settings.block_solution_keys,
                )
        except RuntimeError:
            chunks = []
        transcript_chunks = [c for c in chunks if c.category == Category.LECTURE_TRANSCRIPT]
        references = _references_from_chunks(transcript_chunks, meta, store.summaries_by_prefix)
        matched = []
        intro = "Here's where this comes up in the lectures."
        if not references:
            return _no_match(request)

    history = request.history[-settings.max_history_turns :]
    user = build_lecture_only_user(condensed, references, history=history)
    try:
        prose = llm.chat(LECTURE_ONLY_SYSTEM, user, temperature=0.2)
        if not prose.strip():
            prose = _deterministic_locator(references)
    except LLMError:
        prose = _deterministic_locator(references)

    trace = (
        _assemble_trace(
            request=request,
            condensed=condensed,
            entries=entries,
            enriched=condensed,
            appended_terms=[],
            index=index,
            rtrace=rtrace,
            chunks=chunks,
            marker_map={},
            marker_ids=[],
            used=[],
            framing="",
            prose=prose,
            settings=settings,
        )
        if request.with_trace
        else None
    )

    return QueryResponse(
        mode=request.mode,
        question=request.question,
        matched_concepts=matched,
        intro_text=intro,
        # lecture_only emits markdown with bare [Lecture N @ HH:MM:SS] refs (no [S#] markers);
        # the frontend renders those as text-only chips. marker_map stays empty.
        answer_markdown=prose,
        marker_map=[],
        references=references,
        references_caption="Chronological timeline — open the recording at any timestamp.",
        trace=trace,
    )


# --- Phase-2 trace assembly ----------------------------------------------------------------


def _ranked(items: list[tuple[str, float]]) -> list[RankedChunk]:
    return [RankedChunk(chunk_id=cid, rank=i + 1, score=sc) for i, (cid, sc) in enumerate(items)]


def _assemble_trace(
    *,
    request: QueryRequest,
    condensed: str,
    entries: list[ConceptEntry],
    enriched: str,
    appended_terms: list[str],
    index: HybridIndex,
    rtrace: RetrievalTrace | None,
    chunks: list[RetrievedChunk],
    marker_map: dict[str, CitationRef],
    marker_ids: list[str],
    used: list[CitationRef],
    framing: str,
    prose: str,
    settings: Settings,
) -> PipelineTrace:
    """Assemble the opt-in PipelineTrace from the artifacts already computed in the handlers."""
    dense_by = dict(rtrace.dense) if rtrace else {}
    sparse_by = dict(rtrace.sparse) if rtrace else {}
    cited_markers = set(marker_ids)
    cited_files = {cr.link_target for cr in used if cr.link_target}

    top_k: list[TracedChunk] = []
    cited_vs: list[CitedRetrieved] = []
    for i, c in enumerate(chunks):
        marker = f"S{i + 1}"
        top_k.append(
            TracedChunk(
                chunk_id=c.chunk_id,
                snippet=c.text[:200],
                source_file=c.source_file,
                category=c.category,
                sensitivity=c.sensitivity,
                dense_score=dense_by.get(c.chunk_id),
                sparse_score=sparse_by.get(c.chunk_id),
                rrf_score=c.score,
            )
        )
        cited_vs.append(
            CitedRetrieved(
                source_file=c.source_file,
                marker=marker,
                cited=(marker in cited_markers) or (c.source_file in cited_files),
            )
        )

    g = index.lexical_gate_report(condensed)
    return PipelineTrace(
        original_question=request.question,
        condensed_question=condensed,
        matched_concepts=[
            ConceptTrace(concept=e.concept, mention_count=e.mention_count) for e in entries
        ],
        retrieval_path="concept" if entries else "fallthrough",
        enriched_query=enriched,
        appended_terms=appended_terms,
        lexical_gate=LexicalGate(
            tokens=g.tokens,
            content_tokens=g.content_tokens,
            dropped_stopwords=g.dropped_stopwords,
            in_vocab=g.in_vocab,
            fraction=g.fraction,
            passed=g.passed,
        ),
        dense=_ranked(rtrace.dense if rtrace else []),
        sparse=_ranked(rtrace.sparse if rtrace else []),
        fused=_ranked(rtrace.fused if rtrace else []),
        excluded=[
            ExcludedChunk(chunk_id=cid, reason=r) for cid, r in (rtrace.excluded if rtrace else [])
        ],
        top_k=top_k,
        marker_map=to_marker_payload(marker_map),
        framing_context=framing,
        raw_prose=prose,
        cited_vs_retrieved=cited_vs,
        # Computed identically to /health so the Inspector and StatusPill never disagree.
        index_ready=os.path.exists(f"{settings.chroma_dir}/records.jsonl"),
    )


# --- helpers: chunk -> reference cards -----------------------------------------------------


def _lecture_label_with_date(cr: CitationRef) -> str:
    """"Lecture 17 · Feb 12, 2025" (date omitted when unknown)."""
    label = f"Lecture {cr.lecture_number}" if cr.lecture_number else "Lecture"
    date_h = format_date(cr.date)
    return f"{label} · {date_h}" if date_h else label


def _blurb_for(
    prefix: str | None, timestamp: str | None, summaries_by_prefix: dict[str, LectureSummary]
) -> str:
    """Resolve a per-timestamp blurb from the lecture summary's highlight topics."""
    if not prefix or not timestamp:
        return ""
    summary = summaries_by_prefix.get(prefix)
    if not summary:
        return ""
    for h in summary.highlights:
        if h.timestamp == timestamp:
            return h.topic
    return ""


def _evidence_references(
    used: list[CitationRef], summaries_by_prefix: dict[str, LectureSummary]
) -> list[LectureReference]:
    """Build the "Sources for this answer" cards from the citations the model actually used,
    in first-appearance order, aggregating timestamps per lecture/source (C3)."""
    refs: list[LectureReference] = []
    index_by_key: dict[str, int] = {}
    for cr in used:
        key = cr.link_target or cr.display
        if key not in index_by_key:
            index_by_key[key] = len(refs)
            if cr.kind == "lecture":
                refs.append(
                    LectureReference(
                        lecture_prefix=cr.lecture_prefix or "",
                        lecture_number=cr.lecture_number or 0,
                        lecture_label=_lecture_label_with_date(cr),
                        lecture_title=cr.title or "",
                        transcript_file=cr.link_target,
                        recording_label=recording_label(cr.lecture_prefix or ""),
                        is_first_mention=False,
                        timestamps=[],
                    )
                )
            else:  # material
                refs.append(
                    LectureReference(
                        lecture_prefix="",
                        lecture_number=0,
                        lecture_label=cr.source_label or cr.display,
                        lecture_title=cr.page or "",
                        transcript_file=cr.link_target,
                        recording_label="",
                        is_first_mention=False,
                        timestamps=[],
                    )
                )
        lr = refs[index_by_key[key]]
        already = {t.timestamp for t in lr.timestamps}
        if cr.kind == "lecture" and cr.timestamp and cr.timestamp not in already:
            lr.timestamps.append(
                TimestampRef(
                    timestamp=cr.timestamp,
                    blurb=_blurb_for(cr.lecture_prefix, cr.timestamp, summaries_by_prefix),
                )
            )
    return refs


def _references_from_chunks(
    chunks: list[RetrievedChunk],
    meta: dict[str, LectureMeta],
    summaries_by_prefix: dict[str, LectureSummary],
) -> list[LectureReference]:
    """Build a chronological lecture-only locator from retrieved transcript chunks (A.3)."""
    # prefix -> (representative citation, cited timestamps)
    by_prefix: dict[str, tuple[CitationRef, list[str]]] = {}
    for c in chunks:
        cr = citation_for_chunk(c, meta, summaries_by_prefix)
        if cr.kind != "lecture" or not cr.lecture_prefix:
            continue
        _, ts_list = by_prefix.setdefault(cr.lecture_prefix, (cr, []))
        if cr.timestamp and cr.timestamp not in ts_list:
            ts_list.append(cr.timestamp)

    ordered = sorted(by_prefix.values(), key=lambda s: s[0].lecture_number or 0)
    refs: list[LectureReference] = []
    for i, (cr, ts_list) in enumerate(ordered):
        prefix = cr.lecture_prefix or ""
        ts_sorted = sorted(ts_list)
        refs.append(
            LectureReference(
                lecture_prefix=prefix,
                lecture_number=cr.lecture_number or 0,
                lecture_label=_lecture_label_with_date(cr),
                lecture_title=cr.title or "",
                transcript_file=cr.link_target,
                recording_label=recording_label(prefix),
                is_first_mention=(i == 0),
                timestamps=[
                    TimestampRef(timestamp=ts, blurb=_blurb_for(prefix, ts, summaries_by_prefix))
                    for ts in ts_sorted
                ],
            )
        )
    return refs


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
