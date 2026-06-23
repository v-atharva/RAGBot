"""Parse and link generated lecture summaries.

Each ``generated_summaries/<stem>.md`` is linked to ``transcripts/<stem>.txt`` by the shared
numeric filename prefix. We extract the Key Highlights table (timestamp -> topic chapters) and
every timestamp mentioned, so summaries can drive CAG routing, the KAG-lite concept index, and
deep-dive navigation into the full transcript.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Highlight, LectureSummary

_PREFIX_RE = re.compile(r"^(\d+)")
_TS_RE = re.compile(r"\b(\d{2}:\d{2}:\d{2})\b")
# A Key Highlights table row: | **00:00:36** | ⚠️ topic text |
_HL_ROW_RE = re.compile(r"^\|\s*\**\s*(\d{2}:\d{2}:\d{2})\s*\**\s*\|\s*(.+?)\s*\|\s*$")
# A Key Highlights bullet row: - **[00:00:26]** — topic text
_HL_BULLET_RE = re.compile(
    r"^[-*]\s*\**\s*\[?(\d{2}:\d{2}:\d{2})\]?\s*\**\s*[—–-]\s*(.+?)\s*$"
)
# The Key Highlights section heading (handles "## Key Highlights" with optional emoji).
_HL_HEADING_RE = re.compile(r"^#+\s*.*key\s+highlights", re.I)
_WARN_MARKERS = ("⚠️", "warning", "common mistake")
_KEY_MARKERS = ("✅",)


def _prefix(name: str) -> str | None:
    m = _PREFIX_RE.match(name)
    return m.group(1) if m else None


def link_summaries(
    summaries_dir: str | Path = "generated_summaries",
    transcripts_dir: str | Path = "transcripts",
) -> dict[str, str]:
    """Return a mapping of summary path -> transcript path (or '' when unmatched)."""
    sdir, tdir = Path(summaries_dir), Path(transcripts_dir)
    transcripts = {_prefix(p.name): p for p in tdir.glob("*.txt")}
    mapping: dict[str, str] = {}
    for sp in sorted(sdir.glob("*.md")):
        tp = transcripts.get(_prefix(sp.name))
        mapping[str(sp)] = str(tp) if tp else ""
    return mapping


def parse_summary(path: str | Path, transcript_path: str | Path | None = None) -> LectureSummary:
    p = Path(path)
    body = p.read_text(encoding="utf-8", errors="replace")
    prefix = _prefix(p.name) or ""
    title = _extract_title(body, fallback=p.stem)
    highlights = _parse_highlights(body)
    timestamps = sorted(set(_TS_RE.findall(body)))
    return LectureSummary(
        lecture_prefix=prefix,
        summary_file=p.name,
        transcript_file=Path(transcript_path).name if transcript_path else None,
        title=title,
        body=body,
        highlights=highlights,
        timestamps=timestamps,
    )


def _extract_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return fallback


def _parse_highlights(body: str) -> list[Highlight]:
    """Parse the Key Highlights chapter markers.

    Two formats appear in the corpus: a markdown table (``| **ts** | topic |``) and a bullet
    list (``- **[ts]** — topic``). Table rows are matched anywhere (unambiguous); bullet rows
    are matched only within the Key Highlights section so unrelated timestamped bullets in the
    body aren't captured.
    """
    highlights: list[Highlight] = []
    in_highlights = False
    for line in body.splitlines():
        stripped = line.strip()

        if _HL_HEADING_RE.match(stripped):
            in_highlights = True
            continue
        # A new section heading ends the highlights region.
        if in_highlights and stripped.startswith("#"):
            in_highlights = False

        m = _HL_ROW_RE.match(stripped)
        if not m and in_highlights:
            m = _HL_BULLET_RE.match(stripped)
        if not m:
            continue

        ts, topic = m.group(1), m.group(2).strip()
        low = topic.lower()
        highlights.append(
            Highlight(
                timestamp=ts,
                topic=_clean_topic(topic),
                is_warning=any(mk in topic or mk in low for mk in _WARN_MARKERS),
                is_key=any(mk in topic for mk in _KEY_MARKERS),
            )
        )
    return highlights


def _clean_topic(topic: str) -> str:
    # Strip leading status emojis/markers and surrounding bold markup for clean text.
    topic = re.sub(r"^(⚠️|✅|ℹ️|❌)\s*", "", topic)
    topic = topic.replace("**", "").strip()
    return topic


def load_all(
    summaries_dir: str | Path = "generated_summaries",
    transcripts_dir: str | Path = "transcripts",
) -> list[LectureSummary]:
    """Link and parse every summary, ordered by lecture prefix."""
    mapping = link_summaries(summaries_dir, transcripts_dir)
    out = [parse_summary(sp, tp or None) for sp, tp in mapping.items()]
    out.sort(key=lambda s: int(s.lecture_prefix) if s.lecture_prefix.isdigit() else 0)
    return out
