"""Condense a conversational follow-up into a standalone question (workstream E.2).

A bare follow-up like "what about on Windows?" matches no concept and retrieves poorly. Before
the normal pipeline runs, we rewrite it into a self-contained question using the conversation
history, then feed the *condensed* form into concept-match → fall-through retrieval → synthesis.
This is the classic conversational-RAG "condense question" step. The original phrasing is kept
for display; the condensed form is used only internally.
"""

from __future__ import annotations

from .llm import LLMClient, LLMError
from .schemas import Turn

_CONDENSE_SYSTEM = """\
You rewrite a student's follow-up question into a single, self-contained question, using the \
conversation so far to resolve references like "that", "it", "the same thing", or "what about \
on Windows?". Output ONLY the rewritten question as one line — no preamble, no quotes, no \
explanation. If the follow-up is already self-contained, return it unchanged. Keep it faithful: \
do not add topics the student did not ask about."""


def condense_followup(question: str, history: list[Turn], llm: LLMClient) -> str:
    """Return a standalone version of ``question`` given prior turns. No-op when no history."""
    if not history:
        return question

    convo = "\n".join(f"Q: {t.question.strip()}\nA: {t.answer.strip()[:400]}" for t in history)
    user = (
        f"Conversation so far:\n{convo}\n\n"
        f"Follow-up question: {question}\n\nRewritten standalone question:"
    )
    try:
        rewritten = llm.chat(_CONDENSE_SYSTEM, user, temperature=0.0).strip()
    except LLMError:
        return question  # LLM down -> fall back to the raw follow-up
    # Guard against an empty or chatty rewrite: keep just the first line, fall back if blank.
    first = rewritten.splitlines()[0].strip() if rewritten else ""
    return first or question
