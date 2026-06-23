"""Data models for parsed lecture summaries (the CAG comprehension layer)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Highlight(BaseModel):
    """One row of a summary's Key Highlights table — a timestamped chapter marker."""

    timestamp: str  # HH:MM:SS
    topic: str
    is_warning: bool = False  # row flagged with a warning marker
    is_key: bool = False  # row flagged as a key rule/takeaway


class LectureSummary(BaseModel):
    """A parsed lecture summary, linked to its source transcript."""

    lecture_prefix: str  # numeric prefix shared with the transcript (e.g. "24")
    summary_file: str
    transcript_file: str | None  # None if no matching transcript found
    title: str
    body: str  # full markdown summary text (the CAG payload)
    highlights: list[Highlight] = Field(default_factory=list)
    # All timestamps mentioned anywhere in the summary (for navigation/jumping).
    timestamps: list[str] = Field(default_factory=list)
