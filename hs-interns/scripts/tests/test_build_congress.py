# scripts/tests/test_build_congress.py
import pandas as pd
import pytest

from build_congress_companions import build_companions_frame
from build_congress_mentions import build_mentions_frame
from build_congress_senators import build_senators_frame


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


def test_senate_average_is_the_mean_of_every_serving_senator():
    """UPDATED for I2. This test previously asserted avg2021 == 30, which is
    the mean over the one senator who happened to say "china" that year -- the
    shape of the I2 bug itself. Bob Brown serves in 2021 and never says it, so
    the line labelled "Senate average" must average him in at zero.
    """
    counts = {("A001", 2020): 10, ("A002", 2020): 20, ("A001", 2021): 30}
    names = {"A001": "Alice Adams", "A002": "Bob Brown"}
    serving = {2020: {"A001", "A002"}, 2021: {"A001", "A002"}}
    df = build_senators_frame(counts, names, serving)
    avg2020 = df[(df.senator == "Senate average") & (df.year == 2020)].mentions.iloc[0]
    avg2021 = df[(df.senator == "Senate average") & (df.year == 2021)].mentions.iloc[0]
    assert avg2020 == 15
    assert avg2021 == 15  # (30 + 0) / 2, not 30


def test_file_stays_ragged_by_TENURE():
    """Beat 3 teaches "Josh Hawley only enters in 2019". No zero-fill.

    I2's zero rows do NOT break this, and the two together sharpen it. A
    senator gets a zero row only for years they were serving, so absence now
    means "not in office", where before it conflated "not in office" with
    "served but never said china" (and, per I3, with a name-match failure).
    Bob Brown takes office in 2022, so he has no 2020 row at all.
    """
    counts = {("A001", 2020): 10, ("A002", 2022): 5}
    names = {"A001": "Alice Adams", "A002": "Bob Brown"}
    serving = {2020: {"A001"}, 2022: {"A001", "A002"}}
    df = build_senators_frame(counts, names, serving)
    bob = df[df.senator == "Bob Brown"]
    assert list(bob.year) == [2022]


def test_rows_are_year_sorted_per_senator():
    counts = {("A001", 2022): 1, ("A001", 2020): 2, ("A001", 2021): 3}
    serving = {year: {"A001"} for year in (2020, 2021, 2022)}
    df = build_senators_frame(counts, {"A001": "Alice Adams"}, serving)
    alice = df[df.senator == "Alice Adams"]
    assert list(alice.year) == [2020, 2021, 2022]


def test_unknown_bioguide_raises():
    with pytest.raises(KeyError):
        build_senators_frame({("ZZZZ", 2020): 1}, {"A001": "Alice Adams"}, {})


def test_serving_is_required_so_it_cannot_be_forgotten():
    """Omitting it used to silently fall back to the I2 population."""
    with pytest.raises(TypeError):
        build_senators_frame({("A001", 2020): 1}, {"A001": "Alice Adams"})
