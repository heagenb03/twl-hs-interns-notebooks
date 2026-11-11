# scripts/build_congress_companions.py
"""Pure transform: raw corpus cache -> data/congress_companions.csv.

Co-occurrence definition (documented in PROVENANCE.md): the window is ONE
SPEECH SEGMENT -- a single senator's single turn. If a segment mentions China
at all, every non-stopword in it is a companion. Repeats count, so the ranking
is by frequency.

GovInfo ships whole granules, which are multi-speaker sections -- the
committed 2021 fixture is 19 turns across 10 senators -- so each granule is
split into turns here before any counting. See _granule_segments. That
splitting is unrelated to the splice question below; it exists regardless of
how many raw sources feed this build.

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
Gentzkow cache. The GovInfo coverage gate in build() is unrelated to that
decision and stays: an interrupted GovInfo pull still produces
validator-clean, plausible-looking, wrong output.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from congress_cache import govinfo_range_usable, iter_govinfo_days
from congress_speakers import SPEAKER_RE, split_turns
from congress_tokenize import count_term, top_companions
from twl_common import (
    CONGRESS_ERAS,
    CONGRESS_RAW_GOVINFO,
    CongressDataRefusalError,
    DATA_DIR,
    GOVINFO_ERA_START,
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

    Derived from CONGRESS_ERAS itself (each entry is a decade label like
    "2010s", covering that decade's ten years) rather than hardcoded decade
    branches, so this can never decouple from CONGRESS_ERAS the way it did
    before Task 3a: CONGRESS_ERAS narrowed to ("2010s", "2020s") but this
    function still had 1990s/2000s branches, so a 1990s/2000s year returned a
    era string _empty_era_segments() had no key for -- a KeyError instead of
    the intended skip.

    None fires for any year outside the configured eras (e.g. a stray
    pre-2010 or post-2029 record) -- that must be reported as a skip, never
    silently folded into the nearest era, since an off-by-one at a decade
    boundary is exactly what would move vocabulary between eras and undermine
    Beat 2's shift claim.
    """
    for era in CONGRESS_ERAS:
        decade_start = int(era[:-1])
        if decade_start <= year <= decade_start + 9:
            return era
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

    That mattered doubly back when this build also read a Gentzkow half that
    used one speech per segment: without this split, the window would have
    silently CHANGED DEFINITION at 2017, the old splice year, landing the
    split inside the 2010s era. The splice itself is gone (see the module
    docstring), but the underlying problem is not -- a GovInfo granule is
    still a multi-speaker section, so the split stays required on its own.

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


def build() -> pd.DataFrame:
    """Walk the GovInfo cache, bucket china-bearing segments by era, and write OUT_PATH.

    No splice: see module docstring. Two gates guard this, and they are not the
    same gate. Both raise CongressDataRefusalError -- one domain exception for
    "this build must not run against this data" -- rather than two different
    refusal idioms:

      * The floor guard below is static -- it checks MENTIONS_YEARS itself,
        not the cache. It exists so that if MENTIONS_YEARS is ever widened
        back below GOVINFO_ERA_START, this fails loudly instead of silently
        building a truncated or empty series for the pre-coverage years.
      * The coverage gate (govinfo_range_usable) is the one that survives
        from before the splice was dropped: an interrupted GovInfo pull is
        still the likeliest failure, and it still produces validator-clean,
        plausible-looking, wrong output -- the exact failure this project
        keeps naming. It has to live here in build(), not only in main(), so
        that calling build() directly never bypasses it. main() below catches
        CongressDataRefusalError and turns it into a return code, so its own
        contract (return 1, never propagate) matches build_congress_mentions
        and test_build_cache_gates.py's expectations.

    Every skipped day/granule/segment is counted by reason and printed, per
    this project's rule that dropped data must be reported, never silently
    discarded.
    """
    start_year, end_year = min(MENTIONS_YEARS), max(MENTIONS_YEARS)

    # No splice: the 1994-2016 overlap calibrated to `govinfo_only` on
    # 2026-07-21, so the Gentzkow half is not read. See twl_common.
    # GOVINFO_ERA_START. The COVERAGE gate below is unrelated to the splice
    # and must stay: an interrupted GovInfo pull still yields validator-clean
    # wrong output.
    if start_year < GOVINFO_ERA_START:
        raise CongressDataRefusalError(
            f"MENTIONS_YEARS starts at {start_year}, before GovInfo coverage "
            f"({GOVINFO_ERA_START}). Pre-{GOVINFO_ERA_START} years need a "
            f"Gentzkow splice, which was abandoned. Restore the splice or "
            f"raise the range floor -- do not let these years build empty."
        )

    usable, bad_years = govinfo_range_usable(CONGRESS_RAW_GOVINFO, start_year, end_year)
    if not usable:
        raise CongressDataRefusalError(
            "Cannot build congress_companions.csv: GovInfo cache incomplete "
            f"for {start_year}-{end_year}. Missing or short: {bad_years}\n"
            f"    Cache: {CONGRESS_RAW_GOVINFO}\n"
            "    Produce it with: python scripts/fetch_congress_govinfo.py "
            f"--start-year {start_year} --end-year {end_year}"
        )

    segments_by_era, skips = govinfo_segments_by_era(
        CONGRESS_RAW_GOVINFO, start_year, end_year
    )

    print(
        "GovInfo cache skipped: "
        f"{skips['phantom_marker']} phantom marker(s), "
        f"{skips['bad_json']} bad JSON day(s), "
        f"{skips['granule_no_text']} granule(s) with no text, "
        f"{skips['year_outside_known_eras']} granule(s) with a year "
        "outside CONGRESS_ERAS, "
        f"{skips['no_china_mention']} segment(s) with no china mention"
    )
    print(
        "GovInfo segmentation: "
        f"{skips['granule_without_speaker_headers']} granule(s) had no "
        "speaker headers and were used whole, "
        f"{skips['head_text_segments_dropped']} pre-header head "
        "block(s) dropped carrying "
        f"{skips['head_text_china_dropped']} china mention(s)"
    )

    for era in CONGRESS_ERAS:
        print(f"era '{era}': {len(segments_by_era[era])} china-bearing segment(s)")

    df = build_companions_frame(segments_by_era)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUT_PATH}")
    return df


def main() -> int:
    # build() raises CongressDataRefusalError itself for both refusals (an
    # incomplete GovInfo cache and a pre-coverage year range) -- so calling
    # build() directly cannot bypass either gate; see its docstring. Caught
    # and translated back into a return code here so main()'s own contract --
    # return 1, never propagate -- matches build_congress_mentions.main() and
    # test_build_cache_gates.py's expectations.
    try:
        build()
    except CongressDataRefusalError as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
