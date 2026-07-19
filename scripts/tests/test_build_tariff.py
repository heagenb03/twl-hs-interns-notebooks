import pandas as pd
import pytest

from build_tariff import normalize_prices
from twl_common import EXPECTED_TICKERS


@pytest.fixture
def messy_raw() -> pd.DataFrame:
    """Raw yfinance output: unsorted, wrong column order, full float precision."""
    index = pd.DatetimeIndex(["2017-01-05", "2017-01-03", "2017-01-04"])
    return pd.DataFrame(
        {
            "AAPL": [29.123456, 29.987654, 29.555555],
            "SPY": [227.111111, 225.999999, 226.5],
            "FXI": [35.1, 35.2, 35.3],
            "BA": [158.1, 158.2, 158.3],
            "CAT": [93.1, 93.2, 93.3],
            "SOYB": [19.1, 19.2, 19.3],
        },
        index=index,
    )


def test_index_is_sorted_ascending(messy_raw):
    out = normalize_prices(messy_raw)
    assert out.index.is_monotonic_increasing


def test_index_is_named_date(messy_raw):
    out = normalize_prices(messy_raw)
    assert out.index.name == "date"


def test_columns_are_in_canonical_order(messy_raw):
    out = normalize_prices(messy_raw)
    assert tuple(out.columns) == EXPECTED_TICKERS


def test_prices_are_rounded_to_two_decimals(messy_raw):
    out = normalize_prices(messy_raw)
    assert out.loc[pd.Timestamp("2017-01-03"), "AAPL"] == 29.99
    assert out.loc[pd.Timestamp("2017-01-03"), "SPY"] == 226.0


def test_duplicate_dates_are_dropped_keeping_first(messy_raw):
    dupe = pd.concat([messy_raw, messy_raw.loc[["2017-01-03"]]])
    out = normalize_prices(dupe)
    assert not out.index.has_duplicates
    assert len(out) == 3


def test_rows_with_any_null_are_dropped(messy_raw):
    holed = messy_raw.copy()
    holed.loc[pd.Timestamp("2017-01-04"), "SOYB"] = None
    out = normalize_prices(holed)
    assert len(out) == 2
    assert pd.Timestamp("2017-01-04") not in out.index
