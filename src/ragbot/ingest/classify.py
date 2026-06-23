"""Stage 1 — classify every raw file into a category + sensitivity, with keep/drop decisions.

Rules are intentionally explicit and auditable: the emitted manifest logs why each file was
kept or dropped. Classification is filename- and extension-driven (cheap, deterministic); the
extract stage later confirms image-only PDFs.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Category, Sensitivity, SourceFile

# Files from other courses / other terms that must never enter this course's corpus.
_DROP_PATTERNS = (
    re.compile(r"iste\s*230", re.I),  # different course
    re.compile(r"fall_2024", re.I),  # wrong term (course is Spring 2025)
)

# Solution keys / exam reviews — kept but tagged HIGH so retrieval excludes them in
# assignment-help mode.
_SOLUTION_PATTERNS = (
    re.compile(r"soln", re.I),
    re.compile(r"midterm_review", re.I),
    re.compile(r"final\s*exam\s*review", re.I),
)

# Match an exercise id where the digits are NOT followed by another digit (so PE01_NEW and
# HW1 Part A both work, but we don't grab "PE1" out of "PE10").
_EXERCISE_RE = re.compile(r"\b(PE|HW)(\d{1,2})(?!\d)", re.I)

_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
_DOC_EXTS = {".doc", ".docx"}
_SHEET_EXTS = {".xls", ".xlsx"}

# Filename hints for categories (checked in order; first match wins).
_CATEGORY_HINTS: tuple[tuple[re.Pattern[str], Category], ...] = (
    (re.compile(r"^ch\d+", re.I), Category.TEXTBOOK_CHAPTER),
    (re.compile(r"sql\s*\d+-\d+", re.I), Category.TEXTBOOK_CHAPTER),  # "SQL 63-69"
    (re.compile(r"\b(PE\d|HW\d|HW1\b)", re.I), Category.ASSIGNMENT_PROMPT),
    (re.compile(r"week[\s_]*\d+", re.I), Category.LECTURE_SLIDES),
    (re.compile(r"(normalization|functions|constraints|relational_?algebra|acid|subtypes)", re.I),
     Category.LECTURE_SLIDES),
    (re.compile(r"(example|er\b|uml|crowfoot|crow|transitive|relationship|diagram)", re.I),
     Category.WORKED_EXAMPLE),
)

# Files that are course logistics rather than content.
_ADMIN_PATTERNS = (
    re.compile(r"syllabus", re.I),
    re.compile(r"iste608___spring", re.I),
    re.compile(r"calendar", re.I),
    re.compile(r"^steps", re.I),
)


def classify_file(path: Path) -> SourceFile:
    name = path.name
    ext = path.suffix.lower()
    size = path.stat().st_size if path.exists() else 0

    base = SourceFile(
        path=str(path),
        name=name,
        ext=ext,
        size_bytes=size,
        category=Category.DROP,
    )

    # 1. Hard drops: cross-course / wrong-term noise.
    for pat in _DROP_PATTERNS:
        if pat.search(name):
            base.keep = False
            base.category = Category.DROP
            base.drop_reason = f"cross-course/other-term noise (matched {pat.pattern!r})"
            return base

    # 2. Record any exercise id encoded in the name.
    # Look for an exercise id in the filename, then fall back to the parent folder
    # (e.g. PE10_Workbench/My Guitar Shop.docx belongs to PE10).
    m = _EXERCISE_RE.search(name) or _EXERCISE_RE.search(path.parent.name)
    if m:
        # Normalize to a zero-padded canonical id: PE1 -> PE01, HW1 -> HW01.
        base.exercise_id = f"{m.group(1).upper()}{int(m.group(2)):02d}"
        # A file living under a PE/HW folder is part of that assignment's materials.
        if _EXERCISE_RE.search(path.parent.name) and base.category == Category.DROP:
            base.category = Category.ASSIGNMENT_PROMPT

    # 3. Solution keys -> keep but sensitivity HIGH.
    for pat in _SOLUTION_PATTERNS:
        if pat.search(name):
            base.category = Category.SOLUTION_KEY
            base.sensitivity = Sensitivity.HIGH
            return base

    # 4. Format-driven categories.
    if ext in _IMAGE_EXTS:
        base.category = Category.DIAGRAM_IMAGE
        return base
    if ext == ".sql":
        base.category = Category.SQL_SCRIPT
        return base
    if ext in _SHEET_EXTS:
        base.category = Category.WORKED_EXAMPLE
        return base

    # 5. Admin/logistics.
    for pat in _ADMIN_PATTERNS:
        if pat.search(name):
            base.category = Category.COURSE_ADMIN
            return base

    # 6. Content hints (textbook / assignment / slides / examples).
    for pat, cat in _CATEGORY_HINTS:
        if pat.search(name):
            base.category = cat
            return base

    # 7. Fallback: treat unrecognized docs/text as worked examples (kept, low risk).
    if ext in _DOC_EXTS or ext in {".txt", ".pdf", ".html"}:
        base.category = Category.WORKED_EXAMPLE
        return base

    # Unknown binary (e.g. .mwb MySQL Workbench model) -> drop.
    base.keep = False
    base.drop_reason = f"unsupported binary format ({ext})"
    return base
