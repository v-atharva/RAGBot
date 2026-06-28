"""Unit tests for the citation data model (workstream C1)."""

from __future__ import annotations

from ragbot.ingest.models import Category
from ragbot.retrieve.index import RetrievedChunk
from ragbot.summaries.lecture_meta import LectureMeta, format_date
from ragbot.tutor.citations import (
    build_marker_map,
    citation_for_chunk,
    format_inline,
    format_reference,
    to_marker_payload,
)
from ragbot.tutor.segment import extract_used_markers

# A small in-memory meta map so the tests don't depend on the committed JSON.
_META = {
    "20": LectureMeta(lecture_prefix="20", number=20, date="2025-02-12", title="3rd Normal Form"),
    "01": LectureMeta(lecture_prefix="01", number=1, date=None, title="PE01"),
}


def _chunk(source_file: str, category: Category, citation: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"{source_file}#0",
        text="…",
        source_file=source_file,
        category=category,
        sensitivity="normal",
        citation=citation,
    )


def test_format_date_drops_leading_zero():
    assert format_date("2025-02-12") == "Feb 12, 2025"
    assert format_date("2025-02-03") == "Feb 3, 2025"
    assert format_date(None) is None


def test_transcript_with_date():
    c = _chunk(
        "20_Normalization_3rd.txt", Category.LECTURE_TRANSCRIPT, "[20_Normalization_3rd @ 00:00:02]"
    )
    ref = citation_for_chunk(c, _META, {})
    assert ref.kind == "lecture"
    assert ref.lecture_number == 20
    assert ref.timestamp == "00:00:02"
    assert format_reference(ref) == "Lecture 20 · Feb 12, 2025 @ 00:00:02"
    assert format_inline(ref) == "Lecture 20 · Feb 12 @ 00:00:02"  # inline drops the year


def test_transcript_without_date():
    c = _chunk("01_PE01.txt", Category.LECTURE_TRANSCRIPT, "[01_PE01 @ 00:11:51]")
    ref = citation_for_chunk(c, _META, {})
    assert ref.date is None
    assert format_reference(ref) == "Lecture 1 @ 00:11:51"  # no date segment


def test_textbook_page():
    c = _chunk("Ch03_MySQL.pdf", Category.TEXTBOOK_CHAPTER, "[Ch03_MySQL p.6]")
    ref = citation_for_chunk(c, _META, {})
    assert ref.kind == "material"
    assert ref.source_label == "MySQL Ch. 3"
    assert ref.page == "p.6"
    assert ref.display == "MySQL Ch. 3, p.6"


def test_assignment_doc_strips_numeric_id():
    c = _chunk("HW1 Part B_2245.pdf", Category.ASSIGNMENT_PROMPT, "[HW1 Part B_2245]")
    ref = citation_for_chunk(c, _META, {})
    assert ref.kind == "material"
    assert ref.source_label == "HW1 Part B"
    assert ref.page is None


def test_image_material():
    c = _chunk("verbose.jpg", Category.DIAGRAM_IMAGE, "[verbose]")
    ref = citation_for_chunk(c, _META, {})
    assert ref.kind == "material"
    assert ref.display == "verbose"


def test_marker_resolution_and_hallucinated_id_dropped():
    chunks = [
        _chunk("20_Normalization_3rd.txt", Category.LECTURE_TRANSCRIPT, "[20_x @ 00:00:02]"),
        _chunk("Ch03_MySQL.pdf", Category.TEXTBOOK_CHAPTER, "[Ch03_MySQL p.6]"),
    ]
    marker_map = build_marker_map(chunks, _META, {})
    prose = "Normalization reduces redundancy.[S1] It builds on relational design.[S2] Bogus.[S9]"
    used, marker_ids = extract_used_markers(prose, marker_map)
    # S1 + S2 resolve (in order); S9 is hallucinated and dropped.
    assert marker_ids == ["S1", "S2"]
    assert {u.kind for u in used} == {"lecture", "material"}


def test_to_marker_payload_projects_chips():
    chunks = [_chunk("20_Normalization_3rd.txt", Category.LECTURE_TRANSCRIPT, "[20_x @ 00:00:02]")]
    payload = to_marker_payload(build_marker_map(chunks, _META, {}))
    assert payload[0].marker == "S1"
    assert payload[0].kind == "lecture"
    assert payload[0].inline_display == "Lecture 20 · Feb 12 @ 00:00:02"
    assert payload[0].timestamp == "00:00:02"
