"""Print every data-derived narrative claim ("anchor") the notebooks make.

The intern notebooks hardcode numbers and shape-claims in markdown prose
(e.g. "china mentions climb steeply after 2017", "Marco Rubio pulls away
from the average after ~2018"). Those claims must be recaptured whenever
the underlying data changes. This module is the single source of truth for
computing them from the built CSVs, so a human can diff the printed values
against notebook prose instead of eyeballing charts.

Anchors are informational, not invariants: they feed manual notebook-prose
recapture rather than a pass/fail gate (see validate_data.py for that). A
hardcoded name or shape claim that no longer holds against the data is
still printed — as a loud sentinel string ("ABSENT FROM DATA",
"NEVER CROSSES") — rather than silently dropped, so a human notices and
updates the prose. It is NOT this module's job to make the claim true by
fuzzy-matching or aliasing names.

Usage:  python scripts/print_anchors.py
"""
from __future__ import annotations

import sys

import pandas as pd

from twl_common import DATA_DIR


def congress_anchors() -> dict[str, str]:
    """Every data-derived claim in congress_mentions.ipynb, keyed by beat."""
    mentions = pd.read_csv(DATA_DIR / "congress_mentions.csv")
    companions = pd.read_csv(DATA_DIR / "congress_companions.csv")
    senators = pd.read_csv(DATA_DIR / "congress_senators.csv")

    china = mentions[mentions.term == "china"].sort_values("year")
    out: dict[str, str] = {}

    out["setup/counts"] = (
        f"Loaded {len(mentions)} year-term counts, {len(companions)} companion "
        f"words, {len(senators)} senator-year counts."
    )
    out["setup/terms"] = str(sorted(mentions.term.unique()))
    out["beat1/china_series"] = (
        f"'china': {china.mentions.iloc[0]} mentions in {china.year.iloc[0]} -> "
        f"{china.mentions.iloc[-1]} in {china.year.iloc[-1]} "
        f"(peak: {china.mentions.max()} in {china.loc[china.mentions.idxmax(), 'year']})"
    )
    for era in ("1990s", "2000s", "2010s", "2020s"):
        top3 = (
            companions[companions.era == era]
            .sort_values("count", ascending=False)
            .word.head(3)
            .tolist()
        )
        out[f"beat2/{era}_top_three"] = ", ".join(top3)

    real = senators[senators.senator != "Senate average"]
    top2024 = real[real.year == 2024].sort_values("mentions", ascending=False)
    out["beat3/leaderboard_2024_top5"] = ", ".join(
        f"{r.senator} ({r.mentions})" for r in top2024.head(5).itertuples()
    )
    for name in ("Marco Rubio", "Tom Cotton", "Josh Hawley", "Chuck Schumer"):
        d = real[real.senator == name]
        if len(d) == 0:
            out[f"beat3/{name}"] = "ABSENT FROM DATA - prose must change"
            continue
        peak = d.loc[d.mentions.idxmax()]
        out[f"beat3/{name}"] = (
            f"first year {d.year.min()}, peaked at {peak.mentions} in {peak.year}"
        )

    japan = mentions[mentions.term == "japan"].set_index("year").mentions
    ratio = (china.set_index("year").mentions / japan).dropna()
    crossed = ratio[ratio > 1]
    out["stretch/china_overtook_japan"] = (
        str(crossed.index[0]) if len(crossed) else "NEVER CROSSES - stretch prose must change"
    )
    return out


def main() -> int:
    """Print every anchor section whose source CSVs are present.

    Anchors are informational (they feed manual notebook-prose recapture,
    not a hard data invariant), so a missing set of source CSVs skips that
    section with a note rather than failing the run. Only finding no
    sections at all is treated as an error, mirroring validate_data.py's
    "nothing to check" convention.
    """
    sections: list[tuple[str, dict[str, str]]] = []

    mentions_path = DATA_DIR / "congress_mentions.csv"
    companions_path = DATA_DIR / "congress_companions.csv"
    senators_path = DATA_DIR / "congress_senators.csv"
    if mentions_path.exists() and companions_path.exists() and senators_path.exists():
        sections.append(("congress", congress_anchors()))
    else:
        print(
            "SKIP congress: one or more of congress_mentions.csv, "
            "congress_companions.csv, congress_senators.csv not found"
        )

    if not sections:
        print("No anchor sources found.")
        return 1

    for name, anchors in sections:
        print(f"== {name} ==")
        for key, value in anchors.items():
            print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
