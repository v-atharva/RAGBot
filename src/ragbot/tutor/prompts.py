"""System prompts and user-message builders for the two tutor modes.

Lecture-only is a *when/where* locator: it must NOT explain the concept, only point to where
it is covered (driven by the deterministic reference list). Course-wide writes one cohesive,
self-contained mini-lesson and grounds specific claims against retrieved excerpts using stable
numbered source markers (``[S1]``, ``[S2]`` …) — never raw filename tags, which the model
used to mangle. Markers are resolved back to structured citations after generation.
"""

from __future__ import annotations

from ragbot.retrieve.index import RetrievedChunk

from .citations import CitationRef, format_reference
from .schemas import LectureReference, Turn

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
COURSE-WIDE mode. Write ONE cohesive, self-contained explanation that the student can learn \
from WITHOUT opening any video. Do not print section headers like "PART 1" or "PART 2" — just \
teach.

Answer the question directly and completely, including questions tied to a practice exercise \
(PE) or homework (HW). If the student asks for the solution to an assignment problem, GIVE the \
full worked solution (the SQL, the schema, the normalization steps, etc.) — do not withhold it, \
do not deflect to "where to look", and do not turn it into a Socratic hint. Be a tutor that \
solves the problem and explains how.

Format your answer as GitHub-flavored MARKDOWN: use **bold** for key terms, *italics* for \
emphasis, `inline code` for identifiers/keywords, ```sql fenced code blocks``` for SQL or shell \
commands, and `-`/`1.` lists where they aid clarity. Keep prose in short paragraphs; use a small \
`###` sub-heading only if it genuinely helps. Do NOT wrap the whole answer in a code block.

Your explanation must:
- Explain the concept clearly at the level of an introductory database course.
- Include at least one intuitive ANALOGY that builds intuition.
- Include at least one concrete WORKED EXAMPLE. Strongly prefer the course's OWN examples when \
they appear in the SOURCES below (e.g. a specific table, query, or scenario the instructor \
used); otherwise construct a small clear one.
- Use the FRAMING NOTES only to match how THIS course frames and emphasizes the topic. The \
framing notes are NOT evidence — never cite them.

Grounding rules (important):
- Each SOURCE excerpt is labeled with a bracketed id like [S1], [S2]. When a specific sentence \
rests on a particular excerpt, cite it by placing the id immediately after that sentence, \
e.g. "Every determinant must be a candidate key.[S2]" You may combine ids like [S1][S3].
- Cite ONLY where an excerpt genuinely supports the sentence. Sentences that come from your \
general knowledge need no citation.
- NEVER write a raw filename, a page tag, or a timestamp as a citation, and NEVER invent an \
id or a fact. Use only the [S#] ids that are actually provided.
- Do NOT output a reference/sources list yourself — an authoritative one is appended \
automatically."""


def _render_history(history: list[Turn], *, max_chars: int = 600) -> str:
    """Compact rendering of recent turns for synthesis continuity (E.3)."""
    if not history:
        return ""
    blocks: list[str] = []
    for t in history:
        ans = t.answer.strip().replace("\n", " ")
        if len(ans) > max_chars:
            ans = ans[:max_chars].rstrip() + "…"
        blocks.append(f"Q: {t.question.strip()}\nA: {ans}")
    return "Earlier in this conversation (context only — do not cite):\n" + "\n\n".join(blocks)


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


def build_lecture_only_user(
    question: str, refs: list[LectureReference], history: list[Turn] | None = None
) -> str:
    hist = _render_history(history or [])
    hist_block = f"{hist}\n\n" if hist else ""
    return (
        f"{hist_block}"
        f"Student question: {question}\n\n"
        f"Authoritative coverage data (use only this):\n"
        f"{render_references_for_prompt(refs)}\n"
    )


def render_markered_chunks(
    chunks: list[RetrievedChunk], marker_map: dict[str, CitationRef]
) -> str:
    """Present each retrieved chunk with its stable [S#] id and a human label."""
    if not chunks:
        return "(no excerpts retrieved)"
    blocks: list[str] = []
    for i, c in enumerate(chunks):
        ref = marker_map.get(f"S{i + 1}")
        label = format_reference(ref) if ref else c.citation
        blocks.append(f"[S{i + 1}] ({label})\n{c.text.strip()}")
    return "\n\n".join(blocks)


def build_course_wide_user(
    question: str,
    framing: str,
    chunks: list[RetrievedChunk],
    marker_map: dict[str, CitationRef],
    history: list[Turn] | None = None,
) -> str:
    hist = _render_history(history or [])
    hist_block = f"{hist}\n\n" if hist else ""
    return (
        f"{hist_block}"
        f"Student question: {question}\n\n"
        f"FRAMING NOTES (for understanding only — do NOT cite):\n"
        f"{framing or '(none)'}\n\n"
        f"SOURCES (cite these by their [S#] id, only where they support a sentence):\n"
        f"{render_markered_chunks(chunks, marker_map)}\n"
    )
