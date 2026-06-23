"""Shared data models for the ingestion pipeline.

The pipeline flows: classify -> extract -> normalize/dedup -> chunk -> index.
Each stage enriches these typed records so downstream retrieval can filter on provenance
and sensitivity.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Category(StrEnum):
    """What kind of source a file is, used for routing and retrieval filters."""

    LECTURE_TRANSCRIPT = "lecture_transcript"
    LECTURE_SLIDES = "lecture_slides"
    TEXTBOOK_CHAPTER = "textbook_chapter"
    ASSIGNMENT_PROMPT = "assignment_prompt"
    SOLUTION_KEY = "solution_key"
    SQL_SCRIPT = "sql_script"
    DIAGRAM_IMAGE = "diagram_image"
    WORKED_EXAMPLE = "worked_example"
    COURSE_ADMIN = "course_admin"
    DROP = "drop"


class Sensitivity(StrEnum):
    """Retrieval sensitivity. ``HIGH`` sources (solution keys, exam reviews) are excluded
    from retrieval in assignment-help mode so the tutor cannot leak answers."""

    NORMAL = "normal"
    HIGH = "high"


class SourceFile(BaseModel):
    """A classified source file (output of stage 1)."""

    path: str
    name: str
    ext: str
    size_bytes: int
    category: Category
    sensitivity: Sensitivity = Sensitivity.NORMAL
    keep: bool = True
    drop_reason: str | None = None
    # Populated by the classifier when a filename encodes an exercise id (e.g. PE04, HW3).
    exercise_id: str | None = None


class ExtractedDoc(BaseModel):
    """Text extracted from a source file (output of stage 2)."""

    source: SourceFile
    text: str
    # Page or segment offsets so chunks can cite a page number / timestamp.
    pages: list[PageSpan] = Field(default_factory=list)
    extractor: str = ""
    extract_error: str | None = None


class PageSpan(BaseModel):
    """A page (PDF) or timed segment (transcript) within an extracted document."""

    label: str  # e.g. "p.45" or "00:12:34"
    start: int  # char offset into ExtractedDoc.text
    end: int


class Chunk(BaseModel):
    """A retrievable unit (output of stage 4). Carries full provenance for citations
    and sensitivity-based filtering."""

    chunk_id: str
    text: str
    source_file: str
    category: Category
    sensitivity: Sensitivity
    citation: str  # e.g. "[lecture 24 @ 00:08:12]" or "[Ch05_MySQL p.63]"
    exercise_id: str | None = None


# Resolve forward reference for ExtractedDoc.pages.
ExtractedDoc.model_rebuild()
