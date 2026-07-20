"""Validate frozen CSVs against the invariants the notebooks silently depend on.

Each `validate_*` function returns a list of human-readable problem strings;
an empty list means the frame is valid. `main()` runs every registered check
against the files under `data/` and prints OK/FAIL per file.
"""
from __future__ import annotations

import sys

import pandas as pd

from twl_common import (
    DATA_DIR,
    EVENT_DATES,
    EXPECTED_TICKERS,
    HEADLINE_EVENTS,
    OUTLET_DOMAINS,
    PRICE_END,
    PRICE_START,
)


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


def validate_headlines(
    df: pd.DataFrame, *, require_all_outlets: bool = False
) -> list[str]:
    """Return problems with a headlines frame. Empty means valid.

    require_all_outlets is True for the synthetic file (balanced by
    construction) and False for the real one, where the approved coverage
    policy is take-what-exists-and-document-the-imbalance.
    """
    problems: list[str] = []

    if list(df.columns) != ["event", "outlet", "headline"]:
        problems.append(
            f"columns must be ['event', 'outlet', 'headline'], got {list(df.columns)}"
        )
        return problems

    expected_events = [e for e, _s, _en in HEADLINE_EVENTS]
    expected_outlets = list(OUTLET_DOMAINS)

    unknown_outlets = sorted(set(df.outlet) - set(expected_outlets))
    if unknown_outlets:
        problems.append(
            f"unknown outlet(s) {', '.join(unknown_outlets)}; the notebook "
            "reindexes to a hardcoded list and would silently drop them"
        )

    unknown_events = sorted(set(df.event) - set(expected_events))
    if unknown_events:
        problems.append(f"unknown event(s): {', '.join(unknown_events)}")

    if require_all_outlets:
        missing = [o for o in expected_outlets if o not in set(df.outlet)]
        if missing:
            problems.append(f"missing outlet(s): {', '.join(missing)}")

    # Row order is load-bearing: media_framing picks its default event with
    # list(df.event.unique())[2].
    order = list(df.event.unique())
    if len(order) < 3:
        problems.append(f"only {len(order)} distinct event(s); need at least 3")
    elif order[2] != "Phase One deal":
        problems.append(
            f"the third distinct event in row order is {order[2]!r}, but the "
            "notebook's unique()[2] default requires 'Phase One deal'"
        )

    # train_test_split(stratify=y) raises below 2 rows for any class.
    for outlet, n in df.outlet.value_counts().items():
        if n < 2:
            problems.append(
                f"{outlet} has {n} row(s); train_test_split(stratify=) needs at least 2"
            )

    if (df.headline.fillna("").str.strip() == "").any():
        problems.append("one or more headlines are empty or whitespace-only")

    dupes = df[df.duplicated(subset=["outlet", "headline"], keep=False)]
    if not dupes.empty:
        problems.append(
            f"{len(dupes)} duplicate (outlet, headline) row(s); duplicates leak "
            "between train and test splits"
        )

    return problems


def main() -> int:
    # (name, found, problems) -- found=False means the expected file is
    # absent, which is legitimate before it's been built (exit stays 0), but
    # must be printed as an explicit SKIP rather than silently vanishing
    # from the check list.
    checks: list[tuple[str, bool, list[str]]] = []

    tariff_path = DATA_DIR / "tariff_prices.csv"
    if tariff_path.exists():
        df = pd.read_csv(tariff_path, index_col="date", parse_dates=True)
        checks.append(("tariff_prices.csv", True, validate_tariff(df)))
    else:
        checks.append(("tariff_prices.csv", False, []))

    synthetic_path = DATA_DIR / "headlines.csv"
    if synthetic_path.exists():
        df = pd.read_csv(synthetic_path)
        checks.append(
            ("headlines.csv", True, validate_headlines(df, require_all_outlets=True))
        )
    else:
        checks.append(("headlines.csv", False, []))

    real_path = DATA_DIR / "headlines_real.csv"
    if real_path.exists():
        df = pd.read_csv(real_path)
        checks.append(("headlines_real.csv", True, validate_headlines(df)))
    else:
        checks.append(("headlines_real.csv", False, []))

    # Later plans append congress checks here.

    any_problems = False
    for name, found, problems in checks:
        if not found:
            print(f"SKIP {name} (not found)")
        elif problems:
            any_problems = True
            print(f"FAIL {name}")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"OK   {name}")

    return 1 if any_problems else 0


if __name__ == "__main__":
    sys.exit(main())
