# scripts/build_congress_mentions.py
"""Pure transform: raw corpus caches -> data/congress_mentions.csv.

Corpus-level counts, so no speaker attribution is involved. Safe to re-run.

Two raw caches feed this build:
  - GovInfo CREC granules, 1994-2024: data/_raw/congress_govinfo/{year}/{pkg}.json
  - Gentzkow-Shapiro-Taddy Senate speeches, ~1990-2016:
    data/_raw/congress_gentzkow/speeches_senate_{congress}.jsonl

They overlap 1994-2016. build() NEVER guesses how to join them: the splice
strategy ('concatenate', 'scale', or 'govinfo_only') is always obtained by
calling calibrate_splice.compare_overlap/choose_strategy (Task 7) on the
china sub-series this module gathers itself. A hardcoded or defaulted
strategy is exactly the failure mode that manufactures a step change at
2017, indistinguishable from Beat 1's real headline finding -- see
calibrate_splice.py's module docstring.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from calibrate_splice import (
    OVERLAP_END_YEAR,
    OVERLAP_START_YEAR,
    choose_strategy,
    compare_overlap,
)
from congress_tokenize import count_all_terms
from twl_common import (
    CONGRESS_RAW_GENTZKOW,
    CONGRESS_RAW_GOVINFO,
    DATA_DIR,
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
    counts: dict[int, dict[str, int]] = {}
    skips = {"bad_json": 0, "phantom_marker": 0, "granule_no_text": 0}
    for year in range(start_year, end_year + 1):
        year_dir = raw_dir / str(year)
        if not year_dir.is_dir():
            continue
        year_counts = _empty_term_counts()
        for path in sorted(year_dir.glob("*.json")):
            try:
                day = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                skips["bad_json"] += 1
                continue
            if "granules" not in day:
                skips["phantom_marker"] += 1
                continue
            for granule in day["granules"]:
                text = granule.get("text")
                if not text:
                    skips["granule_no_text"] += 1
                    continue
                _add_counts(year_counts, text)
        counts[year] = year_counts
    return counts, skips


def gentzkow_counts_by_year(
    raw_dir: Path, start_year: int, end_year: int
) -> tuple[dict[int, dict[str, int]], dict[str, int]]:
    """Sum count_all_terms over every Senate speech record in the Gentzkow cache.

    Reads data/_raw/congress_gentzkow/speeches_senate_{congress}.jsonl, one
    record per line. Each record's `date` field (YYYYMMDD) determines its
    year rather than the congress number in the filename, since a single
    Congress can span two calendar years.

    Returns (counts_by_year, skip_counts). A year only gets a key once a
    record with that year is actually seen, so a year with zero matching
    records stays absent for build_mentions_frame to catch, rather than
    silently reporting zero mentions. skip_counts tracks, by reason, every
    line this function declined to count: 'bad_json' (line failed to
    parse), 'bad_date' (missing/malformed date field), 'out_of_range'
    (date outside [start_year, end_year]).
    """
    counts: dict[int, dict[str, int]] = {}
    skips = {"bad_json": 0, "bad_date": 0, "out_of_range": 0}
    for path in sorted(raw_dir.glob("speeches_senate_*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    skips["bad_json"] += 1
                    continue
                date = record.get("date", "")
                if len(date) < 4 or not date[:4].isdigit():
                    skips["bad_date"] += 1
                    continue
                year = int(date[:4])
                if year < start_year or year > end_year:
                    skips["out_of_range"] += 1
                    continue
                year_counts = counts.setdefault(year, _empty_term_counts())
                _add_counts(year_counts, record.get("text", ""))
    return counts, skips


def _govinfo_years_present(raw_dir: Path, years: range) -> bool:
    """True if at least one non-phantom day exists for any year in `years`."""
    for year in years:
        year_dir = raw_dir / str(year)
        if not year_dir.is_dir():
            continue
        if any(
            p for p in year_dir.glob("*.json") if not p.name.endswith(".phantom.json")
        ):
            return True
    return False


def build() -> pd.DataFrame:
    """Walk both raw caches, resolve the Task 7 splice strategy, and write OUT_PATH.

    The splice strategy is never hardcoded or defaulted: it comes from
    calling calibrate_splice.compare_overlap and calibrate_splice.choose_strategy
    on the china sub-series this function gathers from the same walk used to
    build the final counts, so the strategy decision and the merged output
    cannot disagree about what the china series looked like.

    If the strategy comes back 'govinfo_only', this function stops rather
    than silently shrinking MENTIONS_YEARS or padding 1990-1993 with zeros:
    per calibrate_splice's own module docstring, that outcome means
    abandoning the Gentzkow half, dropping 1990-1993, and re-anchoring the
    Japan beat -- a decision for a human, not something to apply silently.

    Every skipped day/granule/speech is counted by reason and printed, per
    this project's rule that dropped data must be reported, never silently
    discarded.
    """
    start_year, end_year = min(MENTIONS_YEARS), max(MENTIONS_YEARS)

    govinfo_counts, govinfo_skips = govinfo_counts_by_year(
        CONGRESS_RAW_GOVINFO, start_year, end_year
    )
    gentzkow_counts, gentzkow_skips = gentzkow_counts_by_year(
        CONGRESS_RAW_GENTZKOW, start_year, end_year
    )

    print(
        "GovInfo cache skipped: "
        f"{govinfo_skips['phantom_marker']} phantom marker(s), "
        f"{govinfo_skips['bad_json']} bad JSON day(s), "
        f"{govinfo_skips['granule_no_text']} granule(s) with no text"
    )
    print(
        "Gentzkow cache skipped: "
        f"{gentzkow_skips['bad_json']} bad JSON line(s), "
        f"{gentzkow_skips['bad_date']} bad/missing date(s), "
        f"{gentzkow_skips['out_of_range']} record(s) outside "
        f"{start_year}-{end_year}"
    )

    overlap_gentzkow = {
        year: counts["china"]
        for year, counts in gentzkow_counts.items()
        if OVERLAP_START_YEAR <= year <= OVERLAP_END_YEAR
    }
    overlap_govinfo = {
        year: counts["china"]
        for year, counts in govinfo_counts.items()
        if OVERLAP_START_YEAR <= year <= OVERLAP_END_YEAR
    }
    comparison = compare_overlap(overlap_gentzkow, overlap_govinfo)
    strategy = choose_strategy(comparison)
    print(f"calibrate_splice.choose_strategy: {strategy}")

    if strategy == "govinfo_only":
        raise RuntimeError(
            "calibrate_splice.choose_strategy returned 'govinfo_only': the "
            "Gentzkow and GovInfo china series diverge unstably over "
            f"{OVERLAP_START_YEAR}-{OVERLAP_END_YEAR}. Per calibrate_splice's "
            "own module docstring, this means abandoning the 1990-2016 "
            "Gentzkow half, dropping 1990-1993 from the mentions build, and "
            "re-anchoring the Japan beat to the 1994-2000 decline. That is a "
            "decision for Heagen, not something build() will apply silently. "
            "STOP and resolve this before re-running the build."
        )

    scale_factor = comparison["mean_ratio"] if strategy == "scale" else None
    if strategy == "scale":
        print(
            f"Applying scale factor {scale_factor:.4f} (govinfo/gentzkow mean "
            "china ratio) to every term in the pre-2017 Gentzkow half, so the "
            "join at 2017 does not manufacture a step change"
        )

    counts_by_year: dict[int, dict[str, int]] = {}
    for year in MENTIONS_YEARS:
        if year <= OVERLAP_END_YEAR:
            source = gentzkow_counts.get(year)
            if source is None:
                continue  # build_mentions_frame raises, naming this year
            if strategy == "scale":
                counts_by_year[year] = {
                    term: round(n * scale_factor) for term, n in source.items()
                }
            else:
                counts_by_year[year] = dict(source)
        else:
            source = govinfo_counts.get(year)
            if source is None:
                continue  # build_mentions_frame raises, naming this year
            counts_by_year[year] = dict(source)

    df = build_mentions_frame(counts_by_year)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUT_PATH}")
    return df


def main() -> int:
    missing = []
    if not _govinfo_years_present(CONGRESS_RAW_GOVINFO, MENTIONS_YEARS):
        missing.append(
            f"  - GovInfo cache missing or empty: {CONGRESS_RAW_GOVINFO}\n"
            "    Produce it with: python scripts/fetch_congress_govinfo.py"
        )
    if not CONGRESS_RAW_GENTZKOW.exists() or not any(
        CONGRESS_RAW_GENTZKOW.glob("speeches_senate_*.jsonl")
    ):
        missing.append(
            f"  - Gentzkow cache missing or empty: {CONGRESS_RAW_GENTZKOW}\n"
            "    Produce it with: python scripts/fetch_congress_gentzkow.py"
        )
    if missing:
        print(
            "Cannot build congress_mentions.csv: required raw cache(s) are "
            "absent.\n" + "\n".join(missing) + "\n\n"
            "These are long-running downloads (the GovInfo pull is roughly "
            "110k requests; the Gentzkow archive is 11.4 GB) and are not "
            "run automatically. See the scripts above for what each one "
            "produces and where."
        )
        return 1

    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
