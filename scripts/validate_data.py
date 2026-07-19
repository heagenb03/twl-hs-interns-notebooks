"""Assert every invariant the intern notebooks silently depend on.

The notebooks are frozen deliverables whose helpers fail QUIETLY when data
assumptions break — a missing sentinel row draws an empty chart rather than
raising. This module turns those silent failures into loud ones.

Usage:  python scripts/validate_data.py
"""
from __future__ import annotations

import sys

import pandas as pd

from twl_common import (
    CONGRESS_ERAS,
    DATA_DIR,
    EVENT_DATES,
    EXPECTED_TICKERS,
    MENTIONS_YEARS,
    TERM_VARIANTS,
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
        if (df[tk].dropna() <= 0).any():
            problems.append(f"{tk} has non-positive price(s)")

    if not isinstance(df.index, pd.DatetimeIndex):
        problems.append("index is not a DatetimeIndex")
        return problems

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


def validate_congress(
    mentions: pd.DataFrame,
    companions: pd.DataFrame,
    senators: pd.DataFrame,
) -> list[str]:
    """Return a list of problems with the three congress frames. Empty means valid.

    Every check here corresponds to a notebook helper that fails QUIETLY.
    """
    problems: list[str] = []
    expected_terms = set(TERM_VARIANTS)
    expected_years = list(MENTIONS_YEARS)

    # --- congress_mentions.csv -------------------------------------------
    bad_case = sorted({t for t in mentions.term.unique() if t != str(t).lower()})
    if bad_case:
        problems.append(
            f"mentions.term must be lowercase; plot_terms compares against "
            f"term.lower() and would never match: {', '.join(bad_case)}"
        )

    actual_terms = set(mentions.term.unique())
    if actual_terms != expected_terms:
        missing = sorted(expected_terms - actual_terms)
        extra = sorted(actual_terms - expected_terms)
        if missing:
            problems.append(f"mentions is missing term(s): {', '.join(missing)}")
        if extra:
            problems.append(f"mentions has unexpected term(s): {', '.join(extra)}")

    dupes = mentions[mentions.duplicated(["term", "year"], keep=False)]
    if len(dupes):
        pairs = sorted({f"{r.term}/{r.year}" for r in dupes.itertuples()})
        problems.append(
            f"duplicate (term, year) rows: {', '.join(pairs[:5])}; plot_ratio "
            "does set_index('year') and duplicates cause a many-to-many join"
        )

    expected_rows = len(expected_terms) * len(expected_years)
    if len(mentions) != expected_rows:
        problems.append(
            f"mentions is not rectangular: {len(mentions)} rows, expected "
            f"{expected_rows} ({len(expected_terms)} terms x {len(expected_years)} years)"
        )

    for term in sorted(actual_terms & expected_terms):
        d = mentions[mentions.term == term]
        if not d.year.is_monotonic_increasing:
            problems.append(
                f"'{term}' rows are not year-sorted; plot_terms reports "
                ".iloc[0]/.iloc[-1] as the series endpoints without sorting"
            )

    japan_zeros = mentions[(mentions.term == "japan") & (mentions.mentions <= 0)]
    if len(japan_zeros):
        years = ", ".join(str(y) for y in sorted(japan_zeros.year))
        problems.append(
            f"japan has zero/negative mentions in {years}; plot_ratio returns "
            "inf on a zero denominator and .dropna() does not catch inf"
        )

    # --- congress_companions.csv -----------------------------------------
    actual_eras = set(companions.era.unique())
    for era in CONGRESS_ERAS:
        if era not in actual_eras:
            problems.append(f"companions is missing era '{era}'")
    for era in sorted(actual_eras):
        n = int((companions.era == era).sum())
        if n != 10:
            problems.append(
                f"era '{era}' has {n} words, expected exactly 10 words; compare_eras "
                "prints a 'top three' from .head(3) and would understate silently"
            )
    cdupes = companions[companions.duplicated(["era", "word"], keep=False)]
    if len(cdupes):
        problems.append(
            "duplicate (era, word) rows would draw two bars with the same label"
        )

    # --- congress_senators.csv -------------------------------------------
    if "Senate average" not in set(senators.senator.unique()):
        problems.append(
            "no literal 'Senate average' row; plot_senator matches it with exact "
            "case and would draw an empty gray dashed line with no error, while "
            "leaderboard would fail to exclude it"
        )
    else:
        avg = senators[senators.senator == "Senate average"]
        real = senators[senators.senator != "Senate average"]
        for year in sorted(real.year.unique()):
            if year not in set(avg.year):
                problems.append(f"no 'Senate average' row for {year}")
                continue
            expected_mean = real[real.year == year].mentions.mean()
            actual_mean = float(avg[avg.year == year].mentions.iloc[0])
            if abs(actual_mean - expected_mean) > 1.0:
                problems.append(
                    f"'Senate average' for {year} is {actual_mean:.1f} but the "
                    f"mean of senators serving that year is {expected_mean:.1f}"
                )

    sdupes = senators[senators.duplicated(["senator", "year"], keep=False)]
    if len(sdupes):
        problems.append("duplicate (senator, year) rows would double-list a senator")

    for name in sorted(senators.senator.unique()):
        d = senators[senators.senator == name]
        if not d.year.is_monotonic_increasing:
            problems.append(f"'{name}' rows are not year-sorted; plot_senator does not sort")
            break

    return problems


def main() -> int:
    """Validate every dataset CSV that is present. Returns 0 if all clean."""
    checks: list[tuple[str, list[str]]] = []

    tariff_path = DATA_DIR / "tariff_prices.csv"
    if tariff_path.exists():
        df = pd.read_csv(tariff_path, index_col="date", parse_dates=True)
        checks.append(("tariff_prices.csv", validate_tariff(df)))

    mentions_path = DATA_DIR / "congress_mentions.csv"
    companions_path = DATA_DIR / "congress_companions.csv"
    senators_path = DATA_DIR / "congress_senators.csv"
    if mentions_path.exists() and companions_path.exists() and senators_path.exists():
        checks.append(
            (
                "congress_*.csv",
                validate_congress(
                    pd.read_csv(mentions_path),
                    pd.read_csv(companions_path),
                    pd.read_csv(senators_path),
                ),
            )
        )

    # Later plans append headlines checks here.

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
