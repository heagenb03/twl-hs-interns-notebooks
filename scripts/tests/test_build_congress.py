# scripts/tests/test_build_congress.py
import pandas as pd
import pytest

from build_congress_companions import build_companions_frame
from build_congress_mentions import build_mentions_frame


def _counts() -> dict[int, dict[str, int]]:
    terms = ["china", "climate", "japan", "russia", "taiwan", "tariff", "terrorism", "trade"]
    return {y: {t: 10 + y % 5 for t in terms} for y in range(1990, 2025)}


def test_frame_is_rectangular_and_sorted():
    df = build_mentions_frame(_counts())
    assert list(df.columns) == ["year", "term", "mentions"]
    assert len(df) == 280
    for term in df.term.unique():
        assert df[df.term == term].year.is_monotonic_increasing


def test_terms_are_lowercase():
    df = build_mentions_frame(_counts())
    assert all(t == t.lower() for t in df.term.unique())


def test_missing_year_raises_rather_than_shipping_a_gap():
    counts = _counts()
    del counts[2001]
    with pytest.raises(ValueError, match="2001"):
        build_mentions_frame(counts)


def test_zero_japan_raises():
    # plot_ratio divides by japan; a zero silently yields inf.
    counts = _counts()
    counts[1999]["japan"] = 0
    with pytest.raises(ValueError, match="japan"):
        build_mentions_frame(counts)


FILLER = ["alpha", "bravo", "charlie", "delta", "echo",
          "foxtrot", "golf", "hotel", "india", "juliet", "kilo"]


def _segments() -> dict[str, list[str]]:
    return {
        "1990s": [f"China trade {w} " * (12 - i) for i, w in enumerate(FILLER)],
        "2000s": [f"China currency {w} " * (12 - i) for i, w in enumerate(FILLER)],
        "2010s": [f"China cyber {w} " * (12 - i) for i, w in enumerate(FILLER)],
        "2020s": [f"China semiconductors {w} " * (12 - i) for i, w in enumerate(FILLER)],
    }


def test_exactly_ten_words_per_era():
    df = build_companions_frame(_segments())
    assert list(df.columns) == ["era", "word", "count"]
    for era in ("1990s", "2000s", "2010s", "2020s"):
        assert (df.era == era).sum() == 10


def test_china_is_never_its_own_companion():
    df = build_companions_frame(_segments())
    assert "china" not in set(df.word)


def test_words_may_repeat_across_eras():
    # Unlike the synthetic file, real data will repeat 'trade' and 'taiwan'.
    # Beat 2 compares top-threes and still works with overlap.
    df = build_companions_frame(_segments())
    assert len(df) == 40


def test_era_with_too_few_distinct_words_raises():
    segments = _segments()
    segments["1990s"] = ["China trade"]
    with pytest.raises(ValueError, match="1990s"):
        build_companions_frame(segments)
