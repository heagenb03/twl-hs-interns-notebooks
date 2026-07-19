import pandas as pd
import pytest

from twl_common import EVENT_DATES, EXPECTED_TICKERS
from validate_data import validate_tariff


@pytest.fixture
def good_prices() -> pd.DataFrame:
    """A minimal frame satisfying every tariff invariant."""
    index = pd.DatetimeIndex(
        sorted(set(pd.bdate_range("2017-01-03", "2020-06-30")) | {
            pd.Timestamp(d) for d in EVENT_DATES
        }),
        name="date",
    )
    return pd.DataFrame(
        {tk: [100.0 + i for i in range(len(index))] for tk in EXPECTED_TICKERS},
        index=index,
    )


def test_good_frame_has_no_problems(good_prices):
    assert validate_tariff(good_prices) == []


def test_missing_ticker_is_reported(good_prices):
    broken = good_prices.drop(columns=["SOYB"])
    problems = validate_tariff(broken)
    assert any("SOYB" in p for p in problems)


def test_extra_ticker_is_reported(good_prices):
    broken = good_prices.assign(TSLA=1.0)
    problems = validate_tariff(broken)
    assert any("TSLA" in p for p in problems)


def test_missing_event_date_is_reported(good_prices):
    broken = good_prices.drop(index=pd.Timestamp("2019-05-06"))
    problems = validate_tariff(broken)
    assert any("2019-05-06" in p for p in problems)


def test_unsorted_index_is_reported(good_prices):
    broken = good_prices.iloc[::-1]
    problems = validate_tariff(broken)
    assert any("sorted" in p.lower() for p in problems)


def test_duplicate_dates_are_reported(good_prices):
    broken = pd.concat([good_prices, good_prices.iloc[[5]]]).sort_index()
    problems = validate_tariff(broken)
    assert any("duplicate" in p.lower() for p in problems)


def test_nulls_are_reported(good_prices):
    broken = good_prices.copy()
    broken.loc[broken.index[10], "BA"] = None
    problems = validate_tariff(broken)
    assert any("null" in p.lower() and "BA" in p for p in problems)


def test_nonpositive_price_is_reported(good_prices):
    broken = good_prices.copy()
    broken.loc[broken.index[10], "CAT"] = 0.0
    problems = validate_tariff(broken)
    assert any("CAT" in p for p in problems)


def test_event_with_no_prior_row_is_reported(good_prices):
    """Every event needs a preceding row — the notebook rebases on iloc[i-1]."""
    broken = good_prices.loc[pd.Timestamp("2018-03-22"):]
    problems = validate_tariff(broken)
    assert any("prior" in p.lower() or "preceding" in p.lower() for p in problems)
