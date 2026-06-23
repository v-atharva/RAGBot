"""Unit tests for the deterministic tutor logic (no LLM / network)."""

from __future__ import annotations

from ragbot.summaries.concepts import ConceptEntry, ConceptLocation
from ragbot.summaries.models import Highlight, LectureSummary
from ragbot.tutor.enrich import enrich_query, framing_context
from ragbot.tutor.llm import strip_think
from ragbot.tutor.prompts import build_lecture_only_user
from ragbot.tutor.references import build_reference_list, lecture_label, recording_label
from ragbot.tutor.schemas import SegmentType
from ragbot.tutor.segment import segment_prose


def _summary(prefix: str, title: str, highlights: list[tuple[str, str]]) -> LectureSummary:
    return LectureSummary(
        lecture_prefix=prefix,
        summary_file=f"{prefix}.md",
        transcript_file=f"{prefix}.txt",
        title=title,
        body="",
        highlights=[Highlight(timestamp=ts, topic=tp) for ts, tp in highlights],
        timestamps=[ts for ts, _ in highlights],
    )


def _entry() -> tuple[ConceptEntry, dict[str, LectureSummary]]:
    summaries = {
        "17": _summary("17", "Normalization", [("00:31:10", "BCNF named in overview")]),
        "24": _summary(
            "24", "BCNF - Last Normal Form", [("00:00:47", "every determinant is a candidate key")]
        ),
    }
    entry = ConceptEntry(
        concept="BCNF",
        locations=[
            ConceptLocation(lecture_prefix="17", lecture_title="Normalization",
                            transcript_file="17.txt", timestamps=["00:31:10"]),
            ConceptLocation(lecture_prefix="24", lecture_title="BCNF - Last Normal Form",
                            transcript_file="24.txt", timestamps=["00:00:47"]),
        ],
        mention_count=2,
    )
    return entry, summaries


def test_lecture_labels():
    assert lecture_label("24") == "Lecture 24"
    assert recording_label("24") == "Recording of Lecture 24"


def test_reference_list_first_mention_and_blurbs():
    entry, summaries = _entry()
    refs = build_reference_list(entry, summaries)
    assert [r.lecture_number for r in refs] == [17, 24]
    # First proper mention is the earliest lecture with a timestamp.
    assert refs[0].is_first_mention is True
    assert refs[1].is_first_mention is False
    # Blurb is resolved from the lecture summary's highlight topic.
    assert refs[1].timestamps[0].blurb == "every determinant is a candidate key"


def test_reference_first_mention_skips_empty_timestamps():
    summaries = {"24": _summary("24", "BCNF", [("00:00:47", "rule")])}
    entry = ConceptEntry(
        concept="BCNF",
        locations=[
            ConceptLocation(lecture_prefix="03", lecture_title="Intro",
                            transcript_file="03.txt", timestamps=[]),
            ConceptLocation(lecture_prefix="24", lecture_title="BCNF",
                            transcript_file="24.txt", timestamps=["00:00:47"]),
        ],
        mention_count=1,
    )
    refs = build_reference_list(entry, summaries)
    # The empty-timestamp location cannot be the first proper mention.
    assert refs[0].is_first_mention is False
    assert refs[1].is_first_mention is True


def test_enrich_query_appends_terms_but_keeps_question():
    entry, summaries = _entry()
    enriched = enrich_query("explain bcnf", [entry], summaries)
    assert enriched.startswith("explain bcnf ")
    assert "bcnf" in enriched.lower()


def test_framing_context_is_summary_derived():
    entry, summaries = _entry()
    framing = framing_context([entry], summaries)
    assert "Lecture 17" in framing
    assert "every determinant is a candidate key" in framing


def test_segment_prose_types_lecture_and_timestamp():
    types = {s.type for s in segment_prose("See [Lecture 24 @ 00:00:47] now.")}
    assert SegmentType.lecture in types
    assert SegmentType.timestamp in types
    # The lecture span carries a clean label.
    lec = next(s for s in segment_prose("[Lecture 24 @ 00:00:47]") if s.type == SegmentType.lecture)
    assert lec.text == "Lecture 24"


def test_strip_think_removes_trace():
    assert strip_think("<think>reasoning</think>Answer.") == "Answer."
    assert strip_think("<think>unclosed reasoning Answer") == ""


def test_build_lecture_only_user_includes_references():
    entry, summaries = _entry()
    refs = build_reference_list(entry, summaries)
    user = build_lecture_only_user("when was bcnf taught?", refs)
    assert "Lecture 24" in user
    assert "00:00:47" in user
