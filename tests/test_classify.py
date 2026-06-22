from pathlib import Path

import pytest

from ragbot.ingest.classify import classify_file
from ragbot.ingest.models import Category, Sensitivity


def _make(tmp_path: Path, name: str, content: bytes = b"x") -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


@pytest.mark.parametrize(
    "name,expected_id",
    [
        ("PE01_NEW_2245.pdf", "PE01"),
        ("PE10_Workbench.pdf", "PE10"),
        ("HW1 Part A Mac 2245.pdf", "HW01"),
        ("HW08.pdf", "HW08"),
    ],
)
def test_exercise_id_normalization(tmp_path, name, expected_id):
    sf = classify_file(_make(tmp_path, name))
    assert sf.exercise_id == expected_id
    assert sf.category == Category.ASSIGNMENT_PROMPT


def test_cross_course_dropped(tmp_path):
    sf = classify_file(_make(tmp_path, "ISTE 230 Standards v3.docx"))
    assert sf.keep is False
    assert sf.category == Category.DROP


def test_wrong_term_dropped(tmp_path):
    sf = classify_file(_make(tmp_path, "Homework_07_Fall_2024.zip"))
    assert sf.keep is False


def test_solution_key_high_sensitivity(tmp_path):
    sf = classify_file(_make(tmp_path, "MoreNormEx-Soln_version2023.pdf"))
    assert sf.category == Category.SOLUTION_KEY
    assert sf.sensitivity == Sensitivity.HIGH
    assert sf.keep is True


def test_textbook_chapter(tmp_path):
    assert classify_file(_make(tmp_path, "Ch05_MySQL.pdf")).category == Category.TEXTBOOK_CHAPTER


def test_diagram_image(tmp_path):
    assert classify_file(_make(tmp_path, "Strong_and_Weak.jpg")).category == Category.DIAGRAM_IMAGE


def test_unsupported_binary_dropped(tmp_path):
    sf = classify_file(_make(tmp_path, "model.mwb"))
    assert sf.keep is False
