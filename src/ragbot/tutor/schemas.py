"""Request/response models for the tutor API.

The answer is returned as **markdown** (``answer_markdown``) plus a ``marker_map`` resolving the
inline ``[S#]`` source markers the model emits. The frontend renders the markdown and swaps each
``[S#]`` for a structured citation chip via ``marker_map`` — so citations stay correct and
clickable without the client regex-guessing over free text.

- ``references`` is the authoritative list of the sources actually cited (lecture number, title,
  timestamps, blurbs), built backend-side from the resolved markers.
- ``coverage_timeline`` is the secondary KAG concept timeline ("where else this appears").
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Mode(StrEnum):
    lecture_only = "lecture_only"  # "when / where was this covered" locator
    course_wide = "course_wide"  # explain, grounded in course materials


class Turn(BaseModel):
    """One prior exchange in the conversation (workstream E)."""

    question: str
    answer: str  # the prior answer's plain text (markdown stripped, [S#] markers removed)


class QueryRequest(BaseModel):
    mode: Mode
    question: str
    history: list[Turn] = Field(default_factory=list)  # oldest -> newest, capped server-side
    with_trace: bool = False  # opt-in: populate QueryResponse.trace (Inspector); default off/fast


class TimestampRef(BaseModel):
    timestamp: str  # "HH:MM:SS"
    blurb: str = ""  # the highlight topic: in what regard it was discussed
    is_warning: bool = False
    is_key: bool = False


class LectureReference(BaseModel):
    lecture_prefix: str  # "24"
    lecture_number: int  # 24
    lecture_label: str  # "Lecture 24"
    lecture_title: str
    transcript_file: str | None = None  # recording/transcript link target
    recording_label: str  # "Recording of Lecture 24"
    is_first_mention: bool = False  # earliest proper (timestamped) mention
    timestamps: list[TimestampRef] = Field(default_factory=list)


class ModelInfo(BaseModel):
    """One model currently resident in Ollama (from /api/ps)."""

    name: str
    size: int = 0  # total bytes
    size_vram: int = 0  # bytes on GPU


class ModelStatus(BaseModel):
    """Whether the configured LLM is loaded, for the StatusPill toggle (Ollama-only)."""

    provider: str
    loaded: bool
    models: list[ModelInfo] = Field(default_factory=list)
    freed_bytes: int | None = None  # best-effort RAM freed by an unload
    error: str | None = None  # set (with HTTP 200) when Ollama is unreachable


class CitationMarker(BaseModel):
    """Resolves one inline ``[S#]`` marker to a render-ready citation chip (frontend)."""

    marker: str  # "S1"
    inline_display: str  # "Lecture 17 · Feb 12 @ 00:00:02" or "MySQL Ch. 3, p.6"
    kind: str  # "lecture" | "material"
    lecture_prefix: str | None = None
    timestamp: str | None = None  # HH:MM:SS
    link_target: str | None = None  # transcript/source file the pill links to


# --- Phase-2 pipeline trace (opt-in via QueryRequest.with_trace) ---


class RankedChunk(BaseModel):
    chunk_id: str
    rank: int
    score: float | None = None


class ExcludedChunk(BaseModel):
    chunk_id: str
    reason: str  # "sensitivity" | "category"


class TracedChunk(BaseModel):
    chunk_id: str
    snippet: str
    source_file: str
    category: str
    sensitivity: str
    dense_score: float | None = None
    sparse_score: float | None = None
    rrf_score: float | None = None


class ConceptTrace(BaseModel):
    concept: str
    mention_count: int


class LexicalGate(BaseModel):
    tokens: list[str] = Field(default_factory=list)
    content_tokens: list[str] = Field(default_factory=list)
    dropped_stopwords: list[str] = Field(default_factory=list)
    in_vocab: list[str] = Field(default_factory=list)
    fraction: float = 0.0
    passed: bool = False


class CitedRetrieved(BaseModel):
    source_file: str
    marker: str | None = None
    cited: bool


class PipelineTrace(BaseModel):
    original_question: str = ""
    condensed_question: str = ""
    matched_concepts: list[ConceptTrace] = Field(default_factory=list)
    retrieval_path: str = ""  # "concept" | "fallthrough"
    enriched_query: str = ""
    appended_terms: list[str] = Field(default_factory=list)
    lexical_gate: LexicalGate | None = None
    dense: list[RankedChunk] = Field(default_factory=list)
    sparse: list[RankedChunk] = Field(default_factory=list)
    fused: list[RankedChunk] = Field(default_factory=list)
    excluded: list[ExcludedChunk] = Field(default_factory=list)
    top_k: list[TracedChunk] = Field(default_factory=list)
    marker_map: list[CitationMarker] = Field(default_factory=list)
    framing_context: str = ""
    raw_prose: str = ""
    cited_vs_retrieved: list[CitedRetrieved] = Field(default_factory=list)
    index_ready: bool = False


class QueryResponse(BaseModel):
    mode: Mode
    question: str
    matched_concepts: list[str] = Field(default_factory=list)
    intro_text: str = ""
    # The model's answer as markdown; inline [S#] markers resolve via ``marker_map``.
    answer_markdown: str = ""
    marker_map: list[CitationMarker] = Field(default_factory=list)
    references: list[LectureReference] = Field(default_factory=list)  # sources actually cited
    references_caption: str = ""
    # KAG concept timeline — "where else this appears in the course" (secondary, collapsible).
    coverage_timeline: list[LectureReference] = Field(default_factory=list)
    coverage_caption: str = ""
    citations: list[str] = Field(default_factory=list)  # raw citation tags of cited chunks
    no_concept_match: bool = False
    trace: PipelineTrace | None = None  # populated only when request.with_trace


class CorpusExplain(BaseModel):
    """Ingestion summary for the Inspector's corpus explainer (from ingest_summary/manifest)."""

    files_seen: int = 0
    transcripts_loaded: int = 0
    kept_docs: int = 0
    chunks: int = 0
    chunks_by_category: dict[str, int] = Field(default_factory=dict)
    high_sensitivity_chunks: int = 0
    high_sensitivity_sources: list[str] = Field(default_factory=list)
    dropped_classify: int = 0
    dropped_dedup: int = 0
    by_format: dict[str, int] = Field(default_factory=dict)  # file extension -> count
    error: str | None = None
