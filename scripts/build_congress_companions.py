# scripts/build_congress_companions.py
"""Pure transform: raw corpus caches -> data/congress_companions.csv.

Co-occurrence definition (documented in PROVENANCE.md): the window is the whole
speech segment. If a segment mentions China at all, every non-stopword in it is
a companion. Repeats count, so the ranking is by frequency.

Two raw caches feed this build, the same two build_congress_mentions.py uses:
  - GovInfo CREC granules, 1994-2024: data/_raw/congress_govinfo/{year}/{pkg}.json
  - Gentzkow-Shapiro-Taddy Senate speeches, ~1990-2016:
    data/_raw/congress_gentzkow/speeches_senate_{congress}.jsonl

They overlap 1994-2016. Unlike build_congress_mentions.py, this module does not
need calibrate_splice's ratio/stability verdict -- there is no per-year count
being scaled across the join. But it still must not let a real speech get
tokenized twice from both caches during the overlap, since that would inflate
some companion words' counts for no reason tied to what was actually said.
So build() partitions the overlap exactly the way build_congress_mentions.py's
build() does regardless of splice strategy: Gentzkow supplies every year up to
and including calibrate_splice.OVERLAP_END_YEAR (2016), GovInfo supplies every
year after it. Each source is walked only across the years it is responsible
for, so no segment is ever counted from both caches.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from calibrate_splice import OVERLAP_END_YEAR
from congress_tokenize import count_term, top_companions
from twl_common import (
    CONGRESS_ERAS,
    CONGRESS_RAW_GENTZKOW,
    CONGRESS_RAW_GOVINFO,
    DATA_DIR,
    MENTIONS_YEARS,
)

OUT_PATH = DATA_DIR / "congress_companions.csv"


def build_companions_frame(segments_by_era: dict[str, list[str]]) -> pd.DataFrame:
    """Top ten china-companion words per era."""
    rows = []
    for era in CONGRESS_ERAS:
        if era not in segments_by_era:
            raise ValueError(f"no speech segments for era '{era}'")
        top = top_companions(segments_by_era[era], n=10)
        if len(top) < 10:
            raise ValueError(
                f"era '{era}' yielded only {len(top)} companion words; "
                "compare_eras prints a 'top three' and the validator requires "
                "exactly 10 per era"
            )
        rows.extend((era, word, int(count)) for word, count in top)
    return pd.DataFrame(rows, columns=["era", "word", "count"])


def _era_for_year(year: int) -> str | None:
    """Map a calendar year to one of CONGRESS_ERAS, or None if it fits none.

    Standard decade boundaries: 1990s is 1990-1999, 2000s is 2000-2009, 2010s
    is 2010-2019, 2020s is 2020-2029. MENTIONS_YEARS (1990-2024) falls
    entirely inside this span, so None only fires for data outside the
    notebook's known range (e.g. a stray pre-1990 or post-2029 record) --
    that must be reported as a skip, never silently folded into the nearest
    era, since an off-by-one at a decade boundary is exactly what would move
    vocabulary between eras and undermine Beat 2's shift claim.
    """
    if 1990 <= year <= 1999:
        return "1990s"
    if 2000 <= year <= 2009:
        return "2000s"
    if 2010 <= year <= 2019:
        return "2010s"
    if 2020 <= year <= 2029:
        return "2020s"
    return None


def _empty_era_segments() -> dict[str, list[str]]:
    return {era: [] for era in CONGRESS_ERAS}


def govinfo_segments_by_era(
    raw_dir: Path, start_year: int, end_year: int
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Bucket every china-bearing Senate granule text into its era, by year.

    Reads data/_raw/congress_govinfo/{year}/{package}.json. Each year's
    directory also holds `{package}.phantom.json` marker files recording
    packages that never existed (see fetch_congress_govinfo.py); those are
    excluded by checking for the "granules" key, NOT by filename pattern,
    per the Task 8/9 briefs. GovInfo granules are Senate-only at fetch time
    (fetch_congress_govinfo.py filters to granuleClass == "SENATE"), so no
    chamber filter is needed here.

    Returns (segments_by_era, skip_counts). skip_counts tracks, by reason,
    every day/granule this function declined to use: 'bad_json' (day file
    failed to parse), 'phantom_marker' (no "granules" key), 'granule_no_text'
    (granule dict missing/empty "text"), 'year_outside_known_eras' (a year
    that maps to no CONGRESS_ERAS bucket), 'no_china_mention' (granule text
    that never mentions china, so it contributes no companion words).
    """
    segments = _empty_era_segments()
    skips = {
        "bad_json": 0,
        "phantom_marker": 0,
        "granule_no_text": 0,
        "year_outside_known_eras": 0,
        "no_china_mention": 0,
    }
    for year in range(start_year, end_year + 1):
        year_dir = raw_dir / str(year)
        if not year_dir.is_dir():
            continue
        era = _era_for_year(year)
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
                if era is None:
                    skips["year_outside_known_eras"] += 1
                    continue
                if not count_term(text, "china"):
                    skips["no_china_mention"] += 1
                    continue
                segments[era].append(text)
    return segments, skips


def gentzkow_segments_by_era(
    raw_dir: Path, start_year: int, end_year: int
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Bucket every china-bearing Senate speech text into its era, by year.

    Reads data/_raw/congress_gentzkow/speeches_senate_{congress}.jsonl, one
    record per line. Each record's `date` field (YYYYMMDD) determines its
    year rather than the congress number in the filename, since a single
    Congress can span two calendar years. Only Senate rows ever reach this
    cache (fetch_congress_gentzkow.py filters chamber == 'S' at fetch time),
    so no chamber filter is needed here.

    Returns (segments_by_era, skip_counts). skip_counts tracks, by reason,
    every line this function declined to use: 'bad_json' (line failed to
    parse), 'bad_date' (missing/malformed date field), 'out_of_range' (date
    outside [start_year, end_year]), 'year_outside_known_eras' (a year inside
    range but mapping to no CONGRESS_ERAS bucket), 'no_china_mention' (speech
    text that never mentions china).
    """
    segments = _empty_era_segments()
    skips = {
        "bad_json": 0,
        "bad_date": 0,
        "out_of_range": 0,
        "year_outside_known_eras": 0,
        "no_china_mention": 0,
    }
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
                era = _era_for_year(year)
                if era is None:
                    skips["year_outside_known_eras"] += 1
                    continue
                text = record.get("text", "")
                if not count_term(text, "china"):
                    skips["no_china_mention"] += 1
                    continue
                segments[era].append(text)
    return segments, skips


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
    """Walk both raw caches, bucket china-bearing segments by era, and write OUT_PATH.

    The Gentzkow/GovInfo overlap (1994-2016) is partitioned the same way
    build_congress_mentions.build() partitions it: Gentzkow supplies every
    year through calibrate_splice.OVERLAP_END_YEAR (2016), GovInfo supplies
    every year after. Each source is only walked across its own range, so no
    segment is ever tokenized from both caches.

    Every skipped day/granule/speech is counted by reason and printed, per
    this project's rule that dropped data must be reported, never silently
    discarded.
    """
    start_year, end_year = min(MENTIONS_YEARS), max(MENTIONS_YEARS)

    gentzkow_segments, gentzkow_skips = gentzkow_segments_by_era(
        CONGRESS_RAW_GENTZKOW, start_year, OVERLAP_END_YEAR
    )
    govinfo_segments, govinfo_skips = govinfo_segments_by_era(
        CONGRESS_RAW_GOVINFO, OVERLAP_END_YEAR + 1, end_year
    )

    print(
        "Gentzkow cache skipped: "
        f"{gentzkow_skips['bad_json']} bad JSON line(s), "
        f"{gentzkow_skips['bad_date']} bad/missing date(s), "
        f"{gentzkow_skips['out_of_range']} record(s) outside "
        f"{start_year}-{OVERLAP_END_YEAR}, "
        f"{gentzkow_skips['year_outside_known_eras']} record(s) with a year "
        "outside CONGRESS_ERAS, "
        f"{gentzkow_skips['no_china_mention']} record(s) with no china mention"
    )
    print(
        "GovInfo cache skipped: "
        f"{govinfo_skips['phantom_marker']} phantom marker(s), "
        f"{govinfo_skips['bad_json']} bad JSON day(s), "
        f"{govinfo_skips['granule_no_text']} granule(s) with no text, "
        f"{govinfo_skips['year_outside_known_eras']} granule(s) with a year "
        "outside CONGRESS_ERAS, "
        f"{govinfo_skips['no_china_mention']} granule(s) with no china mention"
    )

    segments_by_era = {
        era: gentzkow_segments[era] + govinfo_segments[era] for era in CONGRESS_ERAS
    }
    for era in CONGRESS_ERAS:
        print(f"era '{era}': {len(segments_by_era[era])} china-bearing segment(s)")

    df = build_companions_frame(segments_by_era)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUT_PATH}")
    return df


def main() -> int:
    missing = []
    if not CONGRESS_RAW_GENTZKOW.exists() or not any(
        CONGRESS_RAW_GENTZKOW.glob("speeches_senate_*.jsonl")
    ):
        missing.append(
            f"  - Gentzkow cache missing or empty: {CONGRESS_RAW_GENTZKOW}\n"
            "    Produce it with: python scripts/fetch_congress_gentzkow.py"
        )
    govinfo_start, mentions_end = OVERLAP_END_YEAR + 1, max(MENTIONS_YEARS)
    if not _govinfo_years_present(
        CONGRESS_RAW_GOVINFO, range(govinfo_start, mentions_end + 1)
    ):
        missing.append(
            f"  - GovInfo cache missing or empty for {govinfo_start}-{mentions_end}: "
            f"{CONGRESS_RAW_GOVINFO}\n"
            "    Produce it with: python scripts/fetch_congress_govinfo.py"
        )
    if missing:
        print(
            "Cannot build congress_companions.csv: required raw cache(s) are "
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
