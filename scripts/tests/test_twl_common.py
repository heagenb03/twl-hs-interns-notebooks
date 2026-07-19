import pandas as pd
import pytest

from twl_common import EVENT_DATES, EXPECTED_TICKERS, event_day


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
