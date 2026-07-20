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
    dupe_row = messy_raw.loc[["2017-01-03"]].copy()
    dupe_row["AAPL"] = 999.99  # distinct from the original's 29.987654
    dupe = pd.concat([messy_raw, dupe_row])
    out = normalize_prices(dupe)
    assert not out.index.has_duplicates
    assert len(out) == 3
    # "keep first" means the row from the ORIGINAL file position survives,
    # not the later duplicate carrying the sentinel value.
    assert out.loc[pd.Timestamp("2017-01-03"), "AAPL"] == 29.99


def test_rows_with_any_null_are_dropped(messy_raw):
    holed = messy_raw.copy()
    holed.loc[pd.Timestamp("2017-01-04"), "SOYB"] = None
    out = normalize_prices(holed)
    assert len(out) == 2
    assert pd.Timestamp("2017-01-04") not in out.index


def test_missing_expected_ticker_column_drops_all_rows_instead_of_writing_nulls(
    messy_raw,
):
    """A raw pull missing an entire expected ticker must fail loud, not write
    empty cells: reindex must run BEFORE dropna so the resulting all-NaN
    column is caught by dropna(how="any"), dropping every row rather than
    surviving into the CSV as blank values."""
    missing_column = messy_raw.drop(columns=["SOYB"])
    out = normalize_prices(missing_column)
    assert len(out) == 0
    assert tuple(out.columns) == EXPECTED_TICKERS
    assert not out.isna().any().any()


def test_unexpected_extra_column_with_null_does_not_drop_a_complete_row(messy_raw):
    """An extra, non-expected column is discarded by reindex before dropna
    runs, so a null in that extra column must not cause an otherwise-complete
    row to be dropped."""
    extra = messy_raw.copy()
    extra["UNEXPECTED"] = [1.0, None, 3.0]
    out = normalize_prices(extra)
    assert len(out) == 3
    assert "UNEXPECTED" not in out.columns
    assert not out.isna().any().any()
