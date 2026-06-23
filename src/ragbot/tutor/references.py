"""Deterministic reference-list builder.

Turns a ``ConceptEntry`` (chronological-by-lecture locations + timestamps) into the
authoritative ``LectureReference`` list that drives the UI's coloured citation chips. The
model never authors this list, so the references stay correct regardless of what the model
writes. Per-timestamp blurbs are resolved from each lecture summary's highlight topics.

First-mention rule (index-only, per the chosen approach): the earliest lecture whose
locations carry a timestamp is the first proper mention. Locations with no timestamp (a
concept named in a title/body but with no chapter marker) cannot be the first mention.
"""

from __future__ import annotations

from ragbot.summaries.concepts import ConceptEntry
from ragbot.summaries.models import Highlight, LectureSummary

from .schemas import LectureReference, TimestampRef


def lecture_number(prefix: str) -> int:
    return int(prefix) if prefix.isdigit() else 0


def lecture_label(prefix: str) -> str:
    n = lecture_number(prefix)
    return f"Lecture {n}" if n else (prefix or "Lecture")


def recording_label(prefix: str) -> str:
    return f"Recording of {lecture_label(prefix)}"


def build_reference_list(
    entry: ConceptEntry, summaries_by_prefix: dict[str, LectureSummary]
) -> list[LectureReference]:
    refs: list[LectureReference] = []
    first_assigned = False
    for loc in entry.locations:
        summary = summaries_by_prefix.get(loc.lecture_prefix)
        topic_by_ts: dict[str, Highlight] = {}
        if summary:
            for h in summary.highlights:
                topic_by_ts.setdefault(h.timestamp, h)

        ts_refs: list[TimestampRef] = []
        for ts in loc.timestamps:
            hl = topic_by_ts.get(ts)
            ts_refs.append(
                TimestampRef(
                    timestamp=ts,
                    blurb=hl.topic if hl else "",
                    is_warning=hl.is_warning if hl else False,
                    is_key=hl.is_key if hl else False,
                )
            )

        is_first = bool(ts_refs) and not first_assigned
        if is_first:
            first_assigned = True

        refs.append(
            LectureReference(
                lecture_prefix=loc.lecture_prefix,
                lecture_number=lecture_number(loc.lecture_prefix),
                lecture_label=lecture_label(loc.lecture_prefix),
                lecture_title=loc.lecture_title,
                transcript_file=loc.transcript_file,
                recording_label=recording_label(loc.lecture_prefix),
                is_first_mention=is_first,
                timestamps=ts_refs,
            )
        )
    return refs
