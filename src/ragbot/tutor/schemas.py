"""Request/response models for the tutor API.

The response is deliberately *structured* so the frontend can colour-highlight reliably
rather than regex-guessing over free text:

- ``references`` is the authoritative, deterministically-computed list of where a concept is
  covered (lecture number, title, timestamps, blurbs). The coloured citation chips render
  from this — never from the model's prose — so the UI stays correct even if the model
  phrases things loosely.
- ``explanation_segments`` is the model's prose pre-split into typed spans
  (text / lecture / timestamp) so the client colours lecture references and timestamps
  without parsing.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Mode(StrEnum):
    lecture_only = "lecture_only"  # "when / where was this covered" locator
    course_wide = "course_wide"  # explain, grounded in course materials


class QueryRequest(BaseModel):
    mode: Mode
    question: str


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


class SegmentType(StrEnum):
    text = "text"  # plain prose
    lecture = "lecture"  # colour A
    timestamp = "timestamp"  # colour B


class ProseSegment(BaseModel):
    type: SegmentType
    text: str
    lecture_prefix: str | None = None  # set when type == lecture (link target)
    timestamp: str | None = None  # set when type == timestamp


class QueryResponse(BaseModel):
    mode: Mode
    question: str
    matched_concepts: list[str] = Field(default_factory=list)
    intro_text: str = ""
    explanation_segments: list[ProseSegment] = Field(default_factory=list)
    references: list[LectureReference] = Field(default_factory=list)
    references_caption: str = ""
    citations: list[str] = Field(default_factory=list)  # transcript citations used (course-wide)
    no_concept_match: bool = False
