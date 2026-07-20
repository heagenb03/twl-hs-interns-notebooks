"""Validate frozen CSVs against the invariants the notebooks silently depend on.

Each `validate_*` function returns a list of human-readable problem strings;
an empty list means the frame is valid. `main()` runs every registered check
against the files under `data/` and prints OK/FAIL per file.
"""
from __future__ import annotations

import sys

import pandas as pd

from twl_common import DATA_DIR
from fetch_headlines import EVENTS as HEADLINE_EVENTS, OUTLET_DOMAINS


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
    checks: list[tuple[str, list[str]]] = []

    # Later plans append tariff and congress checks here.

    synthetic_path = DATA_DIR / "headlines.csv"
    if synthetic_path.exists():
        df = pd.read_csv(synthetic_path)
        checks.append(
            ("headlines.csv", validate_headlines(df, require_all_outlets=True))
        )

    real_path = DATA_DIR / "headlines_real.csv"
    if real_path.exists():
        df = pd.read_csv(real_path)
        checks.append(("headlines_real.csv", validate_headlines(df)))

    if not checks:
        print("No data files found to validate.")
        return 0

    any_problems = False
    for name, problems in checks:
        if problems:
            any_problems = True
            print(f"FAIL {name}")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"OK   {name}")

    return 1 if any_problems else 0


if __name__ == "__main__":
    sys.exit(main())
