# scripts/build_congress_mentions.py
"""Pure transform: raw corpus cache -> data/congress_mentions.csv.

Corpus-level counts, so no speaker attribution is involved. Safe to re-run.

One raw cache feeds this build: GovInfo CREC granules,
data/_raw/congress_govinfo/{year}/{pkg}.json.

This used to splice a second source (Gentzkow-Shapiro-Taddy Senate speeches,
1990-2016) in over their 1994-2016 overlap. calibrate_splice's own walk of
that overlap returned `govinfo_only` on 2026-07-21 -- GovInfo counts a
consistent ~2x Gentzkow because the Congressional Record interleaves
verbatim legislative text with floor speech inside the same granule, and
Gentzkow extracts only the spoken portions. The splice was abandoned rather
than scaled; see twl_common.GOVINFO_ERA_START. The series now covers
GOVINFO_ERA_START-2024 from GovInfo alone, and this module never reads the
Gentzkow cache. The GovInfo coverage gate below is unrelated to that
decision and stays: an interrupted GovInfo pull still produces
validator-clean, wrong output.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from congress_cache import govinfo_range_usable, iter_govinfo_days
from congress_tokenize import count_all_terms
from twl_common import (
    CONGRESS_RAW_GOVINFO,
    DATA_DIR,
    GOVINFO_ERA_START,
    MENTIONS_YEARS,
    TERM_VARIANTS,
)

OUT_PATH = DATA_DIR / "congress_mentions.csv"

TERMS: tuple[str, ...] = tuple(sorted(TERM_VARIANTS))


def build_mentions_frame(counts_by_year: dict[int, dict[str, int]]) -> pd.DataFrame:
    """Turn {year: {term: count}} into the rectangular, year-sorted deliverable."""
    expected_terms = sorted(TERM_VARIANTS)
    rows = []
    for year in MENTIONS_YEARS:
        if year not in counts_by_year:
            raise ValueError(
                f"no counts for {year}; the notebook plots a continuous "
                f"{min(MENTIONS_YEARS)}-{max(MENTIONS_YEARS)} line and a gap "
                "would silently shorten it"
            )
        for term in expected_terms:
            count = int(counts_by_year[year].get(term, 0))
            if term == "japan" and count <= 0:
                raise ValueError(
                    f"japan has {count} mentions in {year}; plot_ratio divides "
                    "by japan and returns inf, which .dropna() does not catch"
                )
            rows.append((year, term, count))
    return pd.DataFrame(rows, columns=["year", "term", "mentions"]).sort_values(
        ["term", "year"], ignore_index=True
    )


def _empty_term_counts() -> dict[str, int]:
    return {term: 0 for term in TERMS}


def _add_counts(target: dict[str, int], text: str) -> None:
    for term, n in count_all_terms(text).items():
        target[term] = target.get(term, 0) + n


def govinfo_counts_by_year(
    raw_dir: Path, start_year: int, end_year: int
) -> tuple[dict[int, dict[str, int]], dict[str, int]]:
    """Sum count_all_terms over every Senate granule in the GovInfo cache.

    Reads data/_raw/congress_govinfo/{year}/{package}.json. Each year's
    directory also holds `{package}.phantom.json` marker files recording
    packages that never existed (see fetch_congress_govinfo.py); those are
    excluded by checking for the "granules" key, NOT by filename pattern,
    per the Task 8 brief.

    Returns (counts_by_year, skip_counts). A year only gets a key if its
    directory exists on disk -- a year with no cached directory is left
    absent so build_mentions_frame's "missing year" guard can name it,
    rather than silently reporting it as zero mentions. skip_counts tracks,
    by reason, every day/granule this function declined to count:
    'bad_json' (day file failed to parse), 'phantom_marker' (no "granules"
    key), 'granule_no_text' (granule dict missing/empty "text").
    """
    counts: dict[int, dict[str, int]] = {
        year: _empty_term_counts()
        for year in range(start_year, end_year + 1)
        if (raw_dir / str(year)).is_dir()
    }
    skips = {"bad_json": 0, "phantom_marker": 0, "granule_no_text": 0}
    for day in iter_govinfo_days(raw_dir, start_year, end_year, skips):
        for granule in day.granules:
            text = granule.get("text")
            if not text:
                skips["granule_no_text"] += 1
                continue
            _add_counts(counts[day.year], text)
    return counts, skips


def build() -> pd.DataFrame:
    """Walk the GovInfo cache and write OUT_PATH. No splice: see module docstring.

    Two gates guard this, and they are not the same gate:

      * The floor guard below is static -- it checks MENTIONS_YEARS itself,
        not the cache. It exists so that if MENTIONS_YEARS is ever widened
        back below GOVINFO_ERA_START, this fails loudly instead of silently
        building a truncated or empty series for the pre-coverage years.
      * The coverage gate (govinfo_range_usable) is the one that survives
        from before the splice was dropped: an interrupted GovInfo pull is
        still the likeliest failure, and it still produces validator-clean,
        plausible-looking, wrong output. It has to live here in build(), not
        only in main(), so that calling build() directly never bypasses it
        (see test_build_still_refuses_an_incomplete_govinfo_range). main()
        below catches the SystemExit this raises and turns it back into a
        return code, so main()'s own contract (return 1, never propagate)
        is unchanged for callers and for test_build_cache_gates.py.

    Every skipped day/granule is counted by reason and printed, per this
    project's rule that dropped data must be reported, never silently
    discarded.
    """
    start_year, end_year = min(MENTIONS_YEARS), max(MENTIONS_YEARS)

    # No splice: the 1994-2016 overlap calibrated to `govinfo_only` on
    # 2026-07-21, so the Gentzkow half is not read. See twl_common.
    # GOVINFO_ERA_START. The COVERAGE gate below is unrelated to the splice
    # and must stay: an interrupted GovInfo pull still yields validator-clean
    # wrong output.
    if start_year < GOVINFO_ERA_START:
        raise RuntimeError(
            f"MENTIONS_YEARS starts at {start_year}, before GovInfo coverage "
            f"({GOVINFO_ERA_START}). Pre-{GOVINFO_ERA_START} years need a "
            f"Gentzkow splice, which was abandoned. Restore the splice or "
            f"raise the range floor -- do not let these years build empty."
        )

    usable, bad_years = govinfo_range_usable(CONGRESS_RAW_GOVINFO, start_year, end_year)
    if not usable:
        print(
            "Cannot build congress_mentions.csv: GovInfo cache incomplete "
            f"for {start_year}-{end_year}. Missing or short: {bad_years}\n"
            f"    Cache: {CONGRESS_RAW_GOVINFO}\n"
            "    Produce it with: python scripts/fetch_congress_govinfo.py "
            f"--start-year {start_year} --end-year {end_year}"
        )
        sys.exit(1)

    govinfo_counts, govinfo_skips = govinfo_counts_by_year(
        CONGRESS_RAW_GOVINFO, start_year, end_year
    )

    print(
        "GovInfo cache skipped: "
        f"{govinfo_skips['phantom_marker']} phantom marker(s), "
        f"{govinfo_skips['bad_json']} bad JSON day(s), "
        f"{govinfo_skips['granule_no_text']} granule(s) with no text"
    )

    df = build_mentions_frame(govinfo_counts)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUT_PATH}")
    return df


def main() -> int:
    # build() raises SystemExit(1) itself for an incomplete GovInfo cache
    # (so calling build() directly cannot bypass the coverage gate -- see its
    # docstring). Caught and translated back into a return code here so
    # main()'s own contract -- return 1, never propagate -- matches every
    # other build's main() and test_build_cache_gates.py's expectations.
    try:
        build()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
