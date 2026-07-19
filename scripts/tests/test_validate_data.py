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
    assert any("non-positive" in p.lower() and "CAT" in p for p in problems)


def test_event_with_no_prior_row_is_reported(good_prices):
    """Every event needs a preceding row — the notebook rebases on iloc[i-1]."""
    broken = good_prices.loc[pd.Timestamp("2018-03-22"):]
    problems = validate_tariff(broken)
    assert any("prior" in p.lower() or "preceding" in p.lower() for p in problems)


def test_duplicated_event_date_does_not_crash(good_prices):
    """Defect 1 regression.

    Duplicating an event date row breaks index uniqueness AND monotonicity
    (the duplicate lands after the last date). `df.index.get_loc(stamp)` then
    returns an ndarray instead of a scalar, and comparing that ndarray to 0
    with `==` inside an `if` raises
    `ValueError: The truth value of an array with more than one element is
    ambiguous.` The validator must never raise — it must report problems.
    """
    ev = pd.Timestamp(EVENT_DATES[2])
    broken = pd.concat([good_prices, good_prices.loc[[ev]]])

    problems = validate_tariff(broken)  # must not raise

    assert isinstance(problems, list)
    assert all(isinstance(p, str) for p in problems)
    assert any("duplicate" in p.lower() for p in problems)


def test_duplicated_leading_event_date_reports_no_preceding_row(good_prices):
    """Defect 2 regression.

    Trim the frame so an event date sits at position 0 (genuinely no
    preceding row), then duplicate that leading row twice more and re-sort.
    The index stays monotonic but non-unique, so `get_loc` returns
    `slice(0, 3, None)`. `slice(0, 3) == 0` is `False` (no exception), so the
    "no preceding row" problem must still be silently dropped on unfixed
    code and must be reported after the fix.
    """
    ev = pd.Timestamp("2018-03-22")
    trimmed = good_prices.loc[ev:]
    broken = pd.concat(
        [trimmed.loc[[ev]], trimmed.loc[[ev]], trimmed]
    ).sort_index()

    problems = validate_tariff(broken)

    assert any(
        "prior" in p.lower() or "preceding" in p.lower() for p in problems
    )


def test_early_return_does_not_skip_price_checks(good_prices):
    """Defect 3 regression.

    A non-DatetimeIndex frame that also has a null BA price and a negative
    CAT price must report all three problems, not just the index-type
    problem. The null/non-positive-price checks do not depend on index type
    and must not be skipped by the early return.
    """
    broken = good_prices.copy()
    broken.loc[broken.index[10], "BA"] = None
    broken.loc[broken.index[11], "CAT"] = -5.0
    broken.index = pd.RangeIndex(len(broken))

    problems = validate_tariff(broken)

    assert any("index is not a DatetimeIndex" in p for p in problems)
    assert any("null" in p.lower() and "BA" in p for p in problems)
    assert any("non-positive" in p.lower() and "CAT" in p for p in problems)
