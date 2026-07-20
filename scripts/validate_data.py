"""Assert every invariant the intern notebooks silently depend on.

The notebooks are frozen deliverables whose helpers fail QUIETLY when data
assumptions break — a missing sentinel row draws an empty chart rather than
raising. This module turns those silent failures into loud ones.

Usage:  python scripts/validate_data.py
"""
from __future__ import annotations

import sys

import pandas as pd

from twl_common import DATA_DIR, EVENT_DATES, EXPECTED_TICKERS, PRICE_END, PRICE_START


def validate_tariff(df: pd.DataFrame) -> list[str]:
    """Return a list of problems with a tariff price frame. Empty means valid."""
    problems: list[str] = []

    actual = tuple(df.columns)
    missing = [tk for tk in EXPECTED_TICKERS if tk not in actual]
    extra = [tk for tk in actual if tk not in EXPECTED_TICKERS]
    if missing:
        problems.append(f"missing ticker column(s): {', '.join(missing)}")
    if extra:
        problems.append(f"unexpected ticker column(s): {', '.join(extra)}")

    for tk in [t for t in EXPECTED_TICKERS if t in df.columns]:
        n_null = int(df[tk].isna().sum())
        if n_null:
            problems.append(f"{tk} has {n_null} null price(s)")
        non_null = df[tk].dropna()
        if not pd.api.types.is_numeric_dtype(non_null):
            problems.append(f"{tk} is not numeric (dtype: {non_null.dtype})")
            continue
        if (non_null <= 0).any():
            problems.append(f"{tk} has non-positive price(s)")

    if not isinstance(df.index, pd.DatetimeIndex):
        problems.append("index is not a DatetimeIndex")
        return problems

    if len(df.index) > 0:
        expected_start = pd.Timestamp(PRICE_START)
        expected_end = pd.Timestamp(PRICE_END)
        actual_start = df.index.min()
        actual_end = df.index.max()
        if actual_start != expected_start:
            problems.append(
                f"index starts {actual_start.date()}, expected {expected_start.date()}"
            )
        if actual_end != expected_end:
            problems.append(
                f"index ends {actual_end.date()}, expected {expected_end.date()}"
            )

    if not df.index.is_monotonic_increasing:
        problems.append("index is not sorted ascending")
    if df.index.has_duplicates:
        dupes = df.index[df.index.duplicated()].unique()
        problems.append(f"duplicate dates: {', '.join(str(d.date()) for d in dupes)}")

    for date in EVENT_DATES:
        stamp = pd.Timestamp(date)
        if stamp not in df.index:
            problems.append(f"event date {date} is not a row in the index")
            continue
        # get_indexer_for returns EVERY position matching `stamp` and works
        # regardless of whether the index is unique/monotonic (get_loc does
        # not: on a duplicated, non-monotonic index it can return an ndarray,
        # and on a duplicated monotonic index it returns a slice — neither
        # compares safely against an int). The event has no preceding row
        # iff its earliest occurrence sits at position 0.
        positions = df.index.get_indexer_for([stamp])
        if positions.min() == 0:
            problems.append(
                f"event date {date} has no preceding row; the notebook rebases "
                "on iloc[i-1] and would silently wrap to the last row"
            )

    return problems


def main() -> int:
    """Validate every dataset CSV that is present. Returns 0 if all clean."""
    checks: list[tuple[str, list[str]]] = []

    tariff_path = DATA_DIR / "tariff_prices.csv"
    if tariff_path.exists():
        df = pd.read_csv(tariff_path, index_col="date", parse_dates=True)
        checks.append(("tariff_prices.csv", validate_tariff(df)))

    # Later plans append headlines and congress checks here.

    if not checks:
        print("No datasets found to validate.")
        return 1

    failed = False
    for name, problems in checks:
        if problems:
            failed = True
            print(f"FAIL {name}")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"OK   {name}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
