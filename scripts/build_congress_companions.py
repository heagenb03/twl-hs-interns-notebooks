# scripts/build_congress_companions.py
"""Pure transform: raw corpus caches -> data/congress_companions.csv.

Co-occurrence definition (documented in PROVENANCE.md): the window is ONE
SPEECH SEGMENT -- a single senator's single turn. If a segment mentions China
at all, every non-stopword in it is a companion. Repeats count, so the ranking
is by frequency.

The two corpora reach that definition differently, and they must agree or the
window changes at the splice year. Gentzkow ships one speech per record
already. GovInfo ships whole granules, which are multi-speaker sections -- the
committed 2021 fixture is 19 turns across 10 senators -- so each granule is
split into turns here before any counting. See _granule_segments.

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

from calibrate_splice import (
    CALIBRATION_YEARS,
    OVERLAP_END_YEAR,
    govinfo_only_message,
    resolve_strategy,
)
from congress_cache import govinfo_years_usable, iter_govinfo_days
from congress_speakers import SPEAKER_RE, split_turns
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


def _granule_segments(text: str, skips: dict[str, int]) -> list[str]:
    """One GovInfo granule -> the speech segments Beat 2 should measure over.

    A granule is NOT one speech. The committed 2021 fixture is 19 turns across
    10 senators; the 1999 aviation granule mentions china exactly once in 36k
    characters. Treating either as a single co-occurrence window means one
    mention donates every word in a whole day's section, so the GovInfo-era
    top-tens come back as procedural boilerplate and senator surnames --
    measured on that 2021 fixture: presiding, officer, all, legislation, yeas,
    nays, colleagues, cantwell. Per turn, the same granule gives all, america,
    competition, states, research, plant, semiconductors, supply.

    That matters because the Gentzkow half already uses one speech per segment,
    so the window silently CHANGED DEFINITION at 2017 -- the splice year -- and
    the split lands inside the 2010s era.

    Splitting is done here, at the segment layer, with the existing
    regression-covered congress_speakers.split_turns. It is deliberately NOT
    done in congress_tokenize: the tokenizer's single-hyphen behaviour is what
    keeps `most-favored-nation` intact, and that is itself a Beat 2 anchor.

    Two guards, both required:

    (a) A granule that yields no turns falls back to the whole granule. Real
        headerless granules exist (CREC-2023-06-14 is 286 characters and has
        none), and Task 9's synthetic fixture has no headers at all -- all four
        of its tests break without this.

    (b) Text before the first header is dropped by split_turns, and the drop is
        COUNTED. In all three multi-speaker fixtures that head text is the
        page-title block -- 0.7% to 3.9% of the granule, and zero china
        mentions -- so dropping it also removes a known contaminant. But it can
        equally be a continuation of the previous granule's speech, which is
        real content, so the volume lost is reported rather than assumed
        harmless.
    """
    turns = split_turns(text)
    if not turns:
        skips["granule_without_speaker_headers"] += 1
        return [text]

    header = SPEAKER_RE.search(text)
    head = text[: header.start()] if header else ""
    if head.strip():
        skips["head_text_segments_dropped"] += 1
        skips["head_text_china_dropped"] += count_term(head, "china")
    return [segment for _, segment in turns]


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
        "granule_without_speaker_headers": 0,
        "head_text_segments_dropped": 0,
        "head_text_china_dropped": 0,
    }
    for day in iter_govinfo_days(raw_dir, start_year, end_year, skips):
        era = _era_for_year(day.year)
        for granule in day.granules:
            text = granule.get("text")
            if not text:
                skips["granule_no_text"] += 1
                continue
            if era is None:
                skips["year_outside_known_eras"] += 1
                continue
            for segment in _granule_segments(text, skips):
                if not count_term(segment, "china"):
                    skips["no_china_mention"] += 1
                    continue
                segments[era].append(segment)
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

    # I1: the splice verdict gates this build too.
    #
    # Task 9's docstring claimed the year-split "does not require invoking
    # calibrate_splice since that split is identical under every splice
    # outcome". True for `concatenate` and `scale`; FALSE for `govinfo_only`.
    # Under that verdict build_congress_mentions produces nothing, while this
    # build would run to completion over the very Gentzkow years the mentions
    # build just declared untrustworthy -- shipping two of three CSVs built on
    # data the third refused to use.
    #
    # The SCALE factor is deliberately NOT applied here (Heagen, 2026-07-20).
    # A uniform factor cannot reorder a top-ten, so scaling is a no-op in every
    # single-source era -- including 1990s and 2020s, which is the notebook's
    # default comparison. It would only touch the straddling 2010s era, and
    # there it is actively harmful: rounding a scaled count with k < 1 collapses
    # small counts to zero and breaks the ten-word requirement.
    strategy, _ = resolve_strategy(CONGRESS_RAW_GENTZKOW, CONGRESS_RAW_GOVINFO)
    print(f"calibrate_splice.choose_strategy: {strategy}")
    if strategy == "govinfo_only":
        raise RuntimeError(
            govinfo_only_message(
                "build_congress_companions",
                "That makes the 1990s and 2000s eras -- both drawn entirely "
                "from Gentzkow -- untrustworthy for Beat 2's vocabulary-shift "
                "claim, which compares 1990s against 2020s by default. "
                "build_congress_mentions stops on this same verdict; "
                "companions must not quietly ship instead.",
            )
        )

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
        f"{govinfo_skips['no_china_mention']} segment(s) with no china mention"
    )
    print(
        "GovInfo segmentation: "
        f"{govinfo_skips['granule_without_speaker_headers']} granule(s) had no "
        "speaker headers and were used whole, "
        f"{govinfo_skips['head_text_segments_dropped']} pre-header head "
        "block(s) dropped carrying "
        f"{govinfo_skips['head_text_china_dropped']} china mention(s)"
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
    # C1: presence is not completeness. The check this replaced returned True
    # for a single leftover smoke-test day, after which build() completed,
    # printed no error, and wrote a validator-clean 40-row CSV whose 2020s row
    # -- Beat 2's entire 2020s teaching claim -- was derived from one day of
    # Senate business: nato, state, all, one, richard, whereas, united, states,
    # hezbollah, washington. build_congress_senators already used a per-year
    # floor; it was never applied back here.
    required = sorted(set(CALIBRATION_YEARS) | set(range(govinfo_start, mentions_end + 1)))
    usable, bad_years = govinfo_years_usable(CONGRESS_RAW_GOVINFO, required)
    if not usable:
        missing.append(
            f"  - GovInfo cache incomplete. Missing or short: {bad_years}\n"
            f"    Required: {list(CALIBRATION_YEARS)} (splice calibration "
            f"sample) plus {govinfo_start}-{mentions_end} (the data).\n"
            f"    Cache: {CONGRESS_RAW_GOVINFO}\n"
            "    Produce it with: python scripts/fetch_congress_govinfo.py "
            f"--start-year 2010 --end-year {mentions_end}"
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
