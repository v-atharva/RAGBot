"""System prompts and user-message builders for the two tutor modes.

Lecture-only is a *when/where* locator: it must NOT explain the concept, only point to where
it is covered (driven by the deterministic reference list). Course-wide explains first from
the model's own knowledge, then grounds against retrieved transcript excerpts — citing only
those excerpts, never the summary framing notes.
"""

from __future__ import annotations

from ragbot.retrieve.index import RetrievedChunk

from .schemas import LectureReference

LECTURE_ONLY_SYSTEM = """\
You are a teaching assistant for a university Database Design course, operating in \
LECTURE-ONLY ("when / where") mode.

In this mode the student wants to know WHEN and WHERE a topic was discussed in the lectures \
— not an explanation of it. You MUST NOT explain, define, or teach the concept. Do not state \
what it is or how it works, not even one sentence. Only point them to the recordings.

You are given an authoritative, pre-computed list of where the concept appears: a first \
proper mention and later mentions, each with an exact lecture number, timestamp, and a short \
blurb. Use ONLY that data — never invent a lecture, timestamp, or detail, and never add \
explanation of your own.

Respond in this shape, short and timestamp-heavy:
1. One sentence naming where it is FIRST properly covered: \
"First covered in [Lecture N @ HH:MM:SS]."
2. A chronological bulleted list of the later mentions. Each bullet exactly:
   "- [Lecture N @ HH:MM:SS] — <the provided blurb>"
3. One short closing nudge to watch the recording(s) at those timestamps.

Always write lecture references as "Lecture N" and timestamps as HH:MM:SS, keeping the exact \
form [Lecture N @ HH:MM:SS] for every citation."""

COURSE_WIDE_SYSTEM = """\
You are a teaching assistant for a university Database Design course, operating in \
COURSE-WIDE mode. You explain the concept, then ground it in this course's own materials.

Answer in two parts, in order:

PART 1 — EXPLAIN: Using your own knowledge, clearly and concisely explain the concept at the \
level of an introductory database course.

PART 2 — GROUND: Then reconcile your explanation with how THIS course actually teaches it. \
You are given:
  (a) FRAMING NOTES distilled from lecture summaries — use these ONLY to understand the \
course's framing and emphasis. Do NOT cite them; they are not evidence.
  (b) RETRIEVED EXCERPTS from the lecture transcripts and course materials, each tagged with \
a citation like [24_BCNF... @ 00:09:53]. Correct anything in your explanation that conflicts \
with these excerpts, and fill gaps they cover. When a statement rests on an excerpt, cite it \
inline using its exact tag.

Cite ONLY the retrieved excerpts — never the framing notes, and never invent a citation, \
timestamp, or quotation. If the excerpts do not cover a point, rely on your general \
explanation and do not cite. Write in clear prose; use "Lecture N" when naming a lecture. \
Do NOT output a reference list yourself — an authoritative one is appended automatically."""


def render_references_for_prompt(refs: list[LectureReference]) -> str:
    """Render the deterministic reference list as the LLM's source data (lecture-only)."""
    lines: list[str] = []
    for ref in refs:
        if not ref.timestamps:
            continue
        for ts in ref.timestamps:
            is_first = ref.is_first_mention and ts is ref.timestamps[0]
            tag = "[first proper mention]" if is_first else ""
            blurb = f" — {ts.blurb}" if ts.blurb else ""
            lines.append(f"- Lecture {ref.lecture_number} @ {ts.timestamp}{blurb} {tag}".rstrip())
    return "\n".join(lines) if lines else "(no recorded mentions found)"


def build_lecture_only_user(question: str, refs: list[LectureReference]) -> str:
    return (
        f"Student question: {question}\n\n"
        f"Authoritative coverage data (use only this):\n"
        f"{render_references_for_prompt(refs)}\n"
    )


def render_chunks_for_prompt(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no excerpts retrieved)"
    blocks = [f"{c.citation}\n{c.text.strip()}" for c in chunks]
    return "\n\n".join(blocks)


def build_course_wide_user(
    question: str, framing: str, chunks: list[RetrievedChunk]
) -> str:
    return (
        f"Student question: {question}\n\n"
        f"FRAMING NOTES (for understanding only — do NOT cite):\n"
        f"{framing or '(none)'}\n\n"
        f"RETRIEVED EXCERPTS (cite these by their exact tag):\n"
        f"{render_chunks_for_prompt(chunks)}\n"
    )
