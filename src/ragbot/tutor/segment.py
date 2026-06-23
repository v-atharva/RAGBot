"""Split model prose into typed spans for reliable colour rendering.

Scans for three things, in priority order: a full ``[Lecture N @ HH:MM:SS]`` citation, a
standalone ``Lecture N`` reference, and a standalone ``HH:MM:SS`` timestamp. Everything else
is plain text. Because the authoritative chips render from the structured reference list,
imperfect segmentation here only ever degrades to plain text — never to wrong data.
"""

from __future__ import annotations

import re

from .schemas import LectureReference, ProseSegment, SegmentType

_SCAN_RE = re.compile(
    r"(?P<cite>\[\s*Lecture\s+\d+\s*@\s*\d{2}:\d{2}:\d{2}\s*\])"
    r"|(?P<lecture>\bLecture\s+\d+\b)"
    r"|(?P<ts>\b\d{2}:\d{2}:\d{2}\b)"
)
_NUM_RE = re.compile(r"\d+")
_TS_INNER_RE = re.compile(r"\d{2}:\d{2}:\d{2}")


def segment_prose(
    prose: str, references: list[LectureReference] | None = None
) -> list[ProseSegment]:
    prefix_by_num: dict[int, str] = {}
    for ref in references or []:
        prefix_by_num.setdefault(ref.lecture_number, ref.lecture_prefix)

    segments: list[ProseSegment] = []

    def push_text(text: str) -> None:
        if not text:
            return
        if segments and segments[-1].type == SegmentType.text:
            segments[-1].text += text
        else:
            segments.append(ProseSegment(type=SegmentType.text, text=text))

    def push_lecture(num: int) -> None:
        segments.append(
            ProseSegment(
                type=SegmentType.lecture,
                text=f"Lecture {num}",
                lecture_prefix=prefix_by_num.get(num),
            )
        )

    def push_ts(ts: str) -> None:
        segments.append(ProseSegment(type=SegmentType.timestamp, text=ts, timestamp=ts))

    pos = 0
    for m in _SCAN_RE.finditer(prose):
        push_text(prose[pos : m.start()])
        pos = m.end()
        if m.group("cite"):
            inner = m.group("cite")
            num = int(_NUM_RE.search(inner).group())  # type: ignore[union-attr]
            ts = _TS_INNER_RE.search(inner).group()  # type: ignore[union-attr]
            push_text("[")
            push_lecture(num)
            push_text(" @ ")
            push_ts(ts)
            push_text("]")
        elif m.group("lecture"):
            push_lecture(int(_NUM_RE.search(m.group("lecture")).group()))  # type: ignore[union-attr]
        else:
            push_ts(m.group("ts"))
    push_text(prose[pos:])
    return segments
