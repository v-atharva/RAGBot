// Mirrors src/ragbot/tutor/schemas.py — keep in lockstep.

export type Mode = "lecture_only" | "course_wide";

export interface TimestampRef {
  timestamp: string;
  blurb: string;
  is_warning: boolean;
  is_key: boolean;
}

export interface LectureReference {
  lecture_prefix: string;
  lecture_number: number;
  lecture_label: string;
  lecture_title: string;
  transcript_file: string | null;
  recording_label: string;
  is_first_mention: boolean;
  timestamps: TimestampRef[];
}

export type CitationKind = "lecture" | "material";

/** Resolves one inline [S#] marker to a render-ready citation chip. */
export interface CitationMarker {
  marker: string; // "S1"
  inline_display: string; // "Lecture 17 · Feb 12 @ 00:00:02" or "MySQL Ch. 3, p.6"
  kind: CitationKind;
  lecture_prefix?: string | null;
  timestamp?: string | null;
  link_target?: string | null;
}

export interface Turn {
  question: string;
  answer: string;
}

export interface QueryRequest {
  mode: Mode;
  question: string;
  history: Turn[];
  with_trace?: boolean;
}

// --- Phase-2 pipeline trace (mirrors schemas.py) ---

export interface RankedChunk {
  chunk_id: string;
  rank: number;
  score?: number | null;
}

export interface ExcludedChunk {
  chunk_id: string;
  reason: string;
}

export interface TracedChunk {
  chunk_id: string;
  snippet: string;
  source_file: string;
  category: string;
  sensitivity: string;
  dense_score?: number | null;
  sparse_score?: number | null;
  rrf_score?: number | null;
}

export interface ConceptTrace {
  concept: string;
  mention_count: number;
}

export interface LexicalGate {
  tokens: string[];
  content_tokens: string[];
  dropped_stopwords: string[];
  in_vocab: string[];
  fraction: number;
  passed: boolean;
}

export interface CitedRetrieved {
  source_file: string;
  marker?: string | null;
  cited: boolean;
}

export interface PipelineTrace {
  original_question: string;
  condensed_question: string;
  matched_concepts: ConceptTrace[];
  retrieval_path: string;
  enriched_query: string;
  appended_terms: string[];
  lexical_gate: LexicalGate | null;
  dense: RankedChunk[];
  sparse: RankedChunk[];
  fused: RankedChunk[];
  excluded: ExcludedChunk[];
  top_k: TracedChunk[];
  marker_map: CitationMarker[];
  framing_context: string;
  raw_prose: string;
  cited_vs_retrieved: CitedRetrieved[];
  index_ready: boolean;
}

export interface CorpusExplain {
  files_seen: number;
  transcripts_loaded: number;
  kept_docs: number;
  chunks: number;
  chunks_by_category: Record<string, number>;
  high_sensitivity_chunks: number;
  high_sensitivity_sources: string[];
  dropped_classify: number;
  dropped_dedup: number;
  by_format: Record<string, number>;
  error?: string | null;
}

export interface QueryResponse {
  mode: Mode;
  question: string;
  matched_concepts: string[];
  intro_text: string;
  answer_markdown: string;
  marker_map: CitationMarker[];
  references: LectureReference[];
  references_caption: string;
  coverage_timeline: LectureReference[];
  coverage_caption: string;
  citations: string[];
  no_concept_match: boolean;
  trace?: PipelineTrace | null;
}

export interface Health {
  status: string;
  provider: string;
  model: string;
  index_ready: boolean;
  concepts: number;
}

export interface ModelInfo {
  name: string;
  size: number;
  size_vram: number;
}

export interface ModelStatus {
  provider: string;
  loaded: boolean;
  models: ModelInfo[];
  freed_bytes?: number | null;
  error?: string | null;
}
