import pandas as pd
import pytest

from twl_common import CONGRESS_ERAS, MENTIONS_YEARS, TERM_VARIANTS
from validate_data import validate_congress


def _good_mentions() -> pd.DataFrame:
    rows = [
        (y, t, 100 + y % 7)
        for t in sorted(TERM_VARIANTS)
        for y in MENTIONS_YEARS
    ]
    return pd.DataFrame(rows, columns=["year", "term", "mentions"])


def _good_companions() -> pd.DataFrame:
    rows = [
        (era, f"word{i}", 100 - i)
        for era in CONGRESS_ERAS
        for i in range(10)
    ]
    return pd.DataFrame(rows, columns=["era", "word", "count"])


def _good_senators() -> pd.DataFrame:
    rows = []
    for year in range(2010, 2025):
        for name in ("Alice Adams", "Bob Brown"):
            rows.append((name, year, 10))
        rows.append(("Senate average", year, 10))
    return pd.DataFrame(rows, columns=["senator", "year", "mentions"])


def test_clean_frames_produce_no_problems():
    assert validate_congress(_good_mentions(), _good_companions(), _good_senators()) == []


def test_missing_senate_average_sentinel_is_caught():
    # plot_senator does `senators[senators.senator == "Senate average"]` with
    # EXACT case; a miss draws an empty gray line with no error.
    s = _good_senators()
    s = s[s.senator != "Senate average"]
    problems = validate_congress(_good_mentions(), _good_companions(), s)
    assert any("Senate average" in p for p in problems)


def test_wrong_case_sentinel_is_caught():
    s = _good_senators().replace({"Senate average": "Senate Average"})
    problems = validate_congress(_good_mentions(), _good_companions(), s)
    assert any("Senate average" in p for p in problems)


def test_uppercase_term_is_caught():
    # plot_terms lowercases the USER's input but never the column.
    m = _good_mentions()
    m.loc[m.term == "china", "term"] = "China"
    problems = validate_congress(m, _good_companions(), _good_senators())
    assert any("lowercase" in p.lower() for p in problems)


def test_zero_japan_value_is_caught():
    # plot_ratio returns inf on a zero denominator and .dropna() misses inf.
    m = _good_mentions()
    m.loc[(m.term == "japan") & (m.year == 1999), "mentions"] = 0
    problems = validate_congress(m, _good_companions(), _good_senators())
    assert any("japan" in p and "zero" in p.lower() for p in problems)


def test_unsorted_years_are_caught():
    # plot_terms reports .iloc[0]/.iloc[-1] as series endpoints without sorting.
    m = _good_mentions().sort_values(["term", "year"], ascending=[True, False])
    problems = validate_congress(m, _good_companions(), _good_senators())
    assert any("sorted" in p.lower() for p in problems)


def test_non_rectangular_mentions_is_caught():
    m = _good_mentions()
    m = m[~((m.term == "climate") & (m.year == 2001))]
    problems = validate_congress(m, _good_companions(), _good_senators())
    assert any("280" in p or "rectangular" in p.lower() for p in problems)


def test_era_with_wrong_word_count_is_caught():
    # compare_eras prints "top three" from .head(3) and would silently print
    # fewer than three.
    c = _good_companions()
    c = c[~((c.era == "1990s") & (c.word == "word9"))]
    problems = validate_congress(_good_mentions(), c, _good_senators())
    assert any("10 words" in p for p in problems)


def test_missing_era_is_caught():
    c = _good_companions()
    c = c[c.era != "2000s"]
    problems = validate_congress(_good_mentions(), c, _good_senators())
    assert any("2000s" in p for p in problems)


def test_duplicate_term_year_is_caught():
    # plot_ratio does set_index("year"); duplicates cause a many-to-many join.
    m = _good_mentions()
    m = pd.concat([m, m.iloc[[0]]], ignore_index=True)
    problems = validate_congress(m, _good_companions(), _good_senators())
    assert any("duplicate" in p.lower() for p in problems)


def test_senate_average_must_exist_for_every_year():
    s = _good_senators()
    s = s[~((s.senator == "Senate average") & (s.year == 2015))]
    problems = validate_congress(_good_mentions(), _good_companions(), s)
    assert any("2015" in p for p in problems)


def test_senate_average_must_equal_the_mean_of_that_year():
    s = _good_senators()
    s.loc[(s.senator == "Senate average") & (s.year == 2012), "mentions"] = 999
    problems = validate_congress(_good_mentions(), _good_companions(), s)
    assert any("mean" in p.lower() and "2012" in p for p in problems)
