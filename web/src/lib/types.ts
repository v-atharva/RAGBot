// Mirrors src/ragbot/tutor/schemas.py

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

export type SegmentType = "text" | "lecture" | "timestamp";

export interface ProseSegment {
  type: SegmentType;
  text: string;
  lecture_prefix?: string | null;
  timestamp?: string | null;
}

export interface QueryResponse {
  mode: Mode;
  question: string;
  matched_concepts: string[];
  intro_text: string;
  explanation_segments: ProseSegment[];
  references: LectureReference[];
  references_caption: string;
  citations: string[];
  no_concept_match: boolean;
}

export interface Health {
  status: string;
  provider: string;
  model: string;
  index_ready: boolean;
  concepts: number;
}
