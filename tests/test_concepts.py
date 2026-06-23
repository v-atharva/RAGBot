from ragbot.summaries.concepts import _match_concepts, build_concept_index
from ragbot.summaries.models import Highlight, LectureSummary


def _summary(prefix, title, highlights):
    return LectureSummary(
        lecture_prefix=prefix,
        summary_file=f"{prefix}_x.md",
        transcript_file=f"{prefix}_x.txt",
        title=title,
        body="",
        highlights=[Highlight(timestamp=ts, topic=t) for ts, t in highlights],
    )


def test_match_word_boundary():
    # "count" should match as a word, not inside "account".
    assert "aggregate functions" in _match_concepts("the COUNT function")
    assert "aggregate functions" not in _match_concepts("create an account table")


def test_bcnf_aliases():
    assert "BCNF" in _match_concepts("Boyce-Codd normal form")
    assert "BCNF" in _match_concepts("he says boyce-cobb")


def test_build_index_traces_concept_across_lectures():
    summaries = [
        _summary("17", "Normalization Lecture", [("00:00:02", "intro to BCNF")]),
        _summary("24", "BCNF Lecture", [("00:00:47", "every determinant is a candidate key")]),
    ]
    index = build_concept_index(summaries, deadlines_path=None)
    bcnf = next(e for e in index if e.concept == "BCNF")
    assert {loc.lecture_prefix for loc in bcnf.locations} == {"17", "24"}


def test_index_sorted_by_frequency():
    summaries = [
        _summary("01", "x", [("00:00:01", "join"), ("00:00:02", "inner join")]),
        _summary("02", "y", [("00:00:01", "subquery")]),
    ]
    index = build_concept_index(summaries, deadlines_path=None)
    assert index[0].mention_count >= index[-1].mention_count
