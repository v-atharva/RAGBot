"""Citation data model (workstream C1) — the single source of truth for turning a retrieved
chunk into a human-friendly, linkable citation.

Everything downstream (inline citation chips, the "Sources for this answer" list, the
lecture-only locator) consumes :class:`CitationRef` instead of re-parsing ad-hoc filename
tags. A lecture chunk becomes ``"Lecture 17 · Feb 12, 2025 @ 00:00:02"``; a material chunk
becomes ``"MySQL Ch. 3, p.6"``. Dates come from :mod:`ragbot.summaries.lecture_meta` and may
be ``None`` (we never fabricate one).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from ragbot.ingest.models import Category
from ragbot.retrieve.index import RetrievedChunk
from ragbot.summaries.lecture_meta import LectureMeta, format_date
from ragbot.summaries.models import LectureSummary

from .schemas import CitationMarker

_PREFIX_RE = re.compile(r"^(\d+)")
_TS_RE = re.compile(r"(\d{2}:\d{2}:\d{2})")
_PAGE_RE = re.compile(r"\bp\.?\s*(\d+)", re.IGNORECASE)
_CH_RE = re.compile(r"^Ch0*(\d+)[ _](.+)$", re.IGNORECASE)


class CitationRef(BaseModel):
    """A structured, render-ready citation for one retrieved chunk."""

    kind: Literal["lecture", "material"]
    # lecture
    lecture_number: int | None = None
    lecture_prefix: str | None = None
    date: str | None = None  # ISO, may be None
    timestamp: str | None = None  # HH:MM:SS
    # material (pdf/doc/slides/sql/image)
    source_label: str | None = None  # e.g. "MySQL Ch. 3", "HW1 Part B"
    page: str | None = None  # "p.6"
    # shared
    source_file: str  # raw filename, for linking
    title: str | None = None
    display: str  # full human string (reference form, with year)
    link_target: str | None = None  # transcript_file / source_file for the UI


def _clean(s: str) -> str:
    return re.sub(r"[ _]+", " ", s).strip()


def _stem(source_file: str) -> str:
    return source_file.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _material_label(source_file: str) -> str:
    """Derive a clean human label from a material filename.

    ``Ch03_MySQL`` -> "MySQL Ch. 3"; ``HW1 Part B_2245`` -> "HW1 Part B".
    """
    stem = _stem(source_file)
    m = _CH_RE.match(stem)
    if m:
        return f"{_clean(m.group(2))} Ch. {int(m.group(1))}"
    stem = re.sub(r"[ _]\d{3,}$", "", stem)  # drop a trailing numeric id (e.g. _2245)
    return _clean(stem)


def citation_for_chunk(
    chunk: RetrievedChunk,
    meta: dict[str, LectureMeta],
    summaries_by_prefix: dict[str, LectureSummary],
) -> CitationRef:
    """Turn a retrieved chunk into a structured citation."""
    if chunk.category == Category.LECTURE_TRANSCRIPT:
        pm = _PREFIX_RE.match(chunk.source_file)
        prefix = pm.group(1) if pm else None
        lm = meta.get(prefix) if prefix else None
        ts_m = _TS_RE.search(chunk.citation or "")
        timestamp = ts_m.group(1) if ts_m else None
        number = lm.number if lm else (int(prefix) if prefix and prefix.isdigit() else None)
        date = lm.date if lm else None
        title = lm.title if lm else None
        if title is None and prefix and prefix in summaries_by_prefix:
            title = summaries_by_prefix[prefix].title

        disp = f"Lecture {number}" if number else "Lecture"
        date_h = format_date(date)
        if date_h:
            disp += f" · {date_h}"
        if timestamp:
            disp += f" @ {timestamp}"
        return CitationRef(
            kind="lecture",
            lecture_number=number,
            lecture_prefix=prefix,
            date=date,
            timestamp=timestamp,
            source_file=chunk.source_file,
            title=title,
            display=disp,
            link_target=chunk.source_file,
        )

    # Material: pdf / doc / slides / sql / image — never invent a lecture number or date.
    label = _material_label(chunk.source_file)
    pg_m = _PAGE_RE.search(chunk.citation or "")
    page = f"p.{pg_m.group(1)}" if pg_m else None
    disp = label + (f", {page}" if page else "")
    return CitationRef(
        kind="material",
        source_label=label,
        page=page,
        source_file=chunk.source_file,
        title=label,
        display=disp,
        link_target=chunk.source_file,
    )


def format_reference(ref: CitationRef) -> str:
    """Fuller reference-list line (keeps the year)."""
    return ref.display


def format_inline(ref: CitationRef) -> str:
    """Compact inline-chip text. Lectures drop the year: ``Lecture 17 · Feb 12 @ 00:00:02``."""
    if ref.kind == "lecture":
        s = f"Lecture {ref.lecture_number}" if ref.lecture_number else "Lecture"
        date_h = format_date(ref.date)
        if date_h:
            s += f" · {date_h.split(',')[0]}"  # "Feb 12, 2025" -> "Feb 12"
        if ref.timestamp:
            s += f" @ {ref.timestamp}"
        return s
    return ref.display


def build_marker_map(
    chunks: list[RetrievedChunk],
    meta: dict[str, LectureMeta],
    summaries_by_prefix: dict[str, LectureSummary],
) -> dict[str, CitationRef]:
    """Assign stable ``S1..Sn`` markers (retrieval order) to each chunk's citation."""
    return {
        f"S{i + 1}": citation_for_chunk(c, meta, summaries_by_prefix)
        for i, c in enumerate(chunks)
    }


def to_marker_payload(marker_map: dict[str, CitationRef]) -> list[CitationMarker]:
    """Project the marker map into the render-ready chips the frontend resolves ``[S#]`` against."""
    return [
        CitationMarker(
            marker=marker,
            inline_display=format_inline(ref),
            kind=ref.kind,
            lecture_prefix=ref.lecture_prefix,
            timestamp=ref.timestamp,
            link_target=ref.link_target,
        )
        for marker, ref in marker_map.items()
    ]
