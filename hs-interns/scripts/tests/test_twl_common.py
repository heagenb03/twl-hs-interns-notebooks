import re

import pandas as pd
import pytest

from twl_common import (
    CONGRESS_ERAS,
    EVENT_DATES,
    EXPECTED_TICKERS,
    GOVINFO_ERA_START,
    GOVINFO_HTML_URL,
    GOVINFO_MODS_URL,
    MENTIONS_YEARS,
    SENATOR_YEARS,
    TERM_VARIANTS,
    event_day,
)


def test_event_day_returns_exact_match_when_date_is_a_trading_day():
    index = pd.DatetimeIndex(["2019-05-03", "2019-05-06", "2019-05-07"])
    assert event_day(index, "2019-05-06") == pd.Timestamp("2019-05-06")


def test_event_day_rolls_forward_over_a_weekend():
    index = pd.DatetimeIndex(["2019-05-03", "2019-05-06"])
    assert event_day(index, "2019-05-04") == pd.Timestamp("2019-05-06")


def test_event_day_rolls_forward_over_a_market_holiday():
    # 2019-07-04 is a market holiday; the next session is 2019-07-05.
    index = pd.DatetimeIndex(["2019-07-03", "2019-07-05"])
    assert event_day(index, "2019-07-04") == pd.Timestamp("2019-07-05")


def test_event_day_raises_when_date_is_past_the_end_of_the_index():
    index = pd.DatetimeIndex(["2019-05-03", "2019-05-06"])
    with pytest.raises(KeyError):
        event_day(index, "2020-01-01")


def test_expected_tickers_are_the_six_notebook_tickers():
    assert EXPECTED_TICKERS == ("SPY", "FXI", "BA", "CAT", "SOYB", "AAPL")


def test_event_dates_are_the_six_announcement_dates():
    assert EVENT_DATES == (
        "2018-03-22",
        "2018-06-15",
        "2018-12-03",
        "2019-05-06",
        "2019-08-23",
        "2020-01-15",
    )


def test_term_variants_cover_the_eight_notebook_terms():
    assert set(TERM_VARIANTS) == {
        "china", "climate", "japan", "russia",
        "taiwan", "tariff", "terrorism", "trade",
    }
    assert all(t == t.lower() for t in TERM_VARIANTS)


def test_term_variants_are_compilable_word_boundary_patterns():
    for term, pattern in TERM_VARIANTS.items():
        rx = re.compile(pattern)
        assert rx.search(term), f"{term} pattern does not match its own name"


def test_year_spans_match_the_notebook():
    assert list(MENTIONS_YEARS) == list(range(2010, 2025))
    assert list(SENATOR_YEARS) == list(range(2010, 2025))
    assert CONGRESS_ERAS == ("2010s", "2020s")


def test_mentions_years_never_predates_govinfo_era():
    """MENTIONS_YEARS below 2010 would need a Gentzkow splice that no longer exists.

    The builds read GovInfo only. If someone widens this range back into the
    Gentzkow era without restoring the splice, every pre-2010 year would come
    back silently empty or truncated -- valid output, plausible values, wrong
    data, which is this project's signature failure.
    """
    assert min(MENTIONS_YEARS) >= GOVINFO_ERA_START


def test_eras_match_the_year_range():
    assert CONGRESS_ERAS == ("2010s", "2020s")
    assert min(MENTIONS_YEARS) == 2010
    assert max(MENTIONS_YEARS) == 2024


def test_govinfo_urls_use_the_keyless_bulk_paths():
    mods = GOVINFO_MODS_URL.format(pkg="CREC-2023-06-14")
    html = GOVINFO_HTML_URL.format(pkg="CREC-2023-06-14", granule="CREC-2023-06-14-pt1-PgS2079-8")
    assert mods == "https://www.govinfo.gov/metadata/pkg/CREC-2023-06-14/mods.xml"
    assert html == (
        "https://www.govinfo.gov/content/pkg/CREC-2023-06-14/html/"
        "CREC-2023-06-14-pt1-PgS2079-8.htm"
    )
    assert "api_key" not in mods and "api_key" not in html
    # MODS lives under /metadata/, text under /content/. Swapping them 404s.
    assert "/metadata/pkg/" in mods
    assert "/content/pkg/" in html
