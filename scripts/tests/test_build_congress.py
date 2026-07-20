# scripts/tests/test_build_congress.py
import pandas as pd
import pytest

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
