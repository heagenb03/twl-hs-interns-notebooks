# scripts/calibrate_splice.py
"""Decide whether the 1990-2016 Gentzkow half and the 2017+ GovInfo half can be
spliced at all.

Both corpora cover 1994-2016, so that window is a genuine overlap. If the two
series disagree there, concatenating them at 2017 would manufacture a step
change indistinguishable from the notebook's headline finding.

Outcomes:
  concatenate  - series agree within a few percent; join directly
  scale        - series differ by a STABLE ratio; apply a documented factor
  govinfo_only - series diverge unstably; abandon the splice, build 1994-2024
                 from GovInfo alone, lose 1990-1993, and re-anchor the Japan
                 beat to the 1994-2000 decline
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from congress_cache import (
    coverage_report,
    govinfo_years_usable,
    iter_govinfo_days,
)
from congress_tokenize import count_term
from twl_common import CONGRESS_RAW_GENTZKOW, CONGRESS_RAW_GOVINFO

AGREE_TOLERANCE = 0.05   # mean |relative difference| under 5% -> concatenate
STABLE_CV = 0.10         # coefficient of variation of the ratio under 10% -> scale

OVERLAP_START_YEAR = 1994
OVERLAP_END_YEAR = 2016  # inclusive
TERM = "china"

CALIBRATION_YEARS: tuple[int, ...] = (
    1994, 1998, 2002, 2006,          # sparse probes across 1994-2009
    2010, 2011, 2012, 2013, 2014, 2015, 2016,  # needed for the roster anyway
)
"""The overlap years the verdict is actually computed on.

The two corpora overlap across all of 1994-2016, but pulling every GovInfo year
in that window costs roughly 32 hours serial and NONE of it reaches a published
CSV -- Gentzkow supplies every pre-2017 count. Those years exist purely to
calibrate. 2010-2016 is the exception: build_congress_senators needs it for the
bioguide roster and the serving set, so it is data and free to calibrate on.

Hence 2010-2016 in full, plus sparse probes back through 1994. Two properties
matter, and the second is why this is a SAMPLE rather than a shorter window:

  * The scale factor is applied to all of 1990-2016. A factor fitted only to a
    contiguous 2010-2016 window would be extrapolated back twenty years with
    nothing testing it. Keeping probes at 1994/1998/2002/2006 means the
    calibration SPANS the era the factor is applied to.
  * cv is a measure of whether the two corpora TRACK each other, not whether
    they happen to agree once. That only means something across the span. If
    the relationship in 1994 differs from 2016, cv rises and the verdict moves
    to govinfo_only instead of silently scaling the 1990s by a 2010s factor.

Widening this back to the full range is always safe and always more expensive.
Narrowing it further -- dropping the pre-2000 probe in particular -- removes the
only thing that would detect a 1990s-specific divergence.
"""

MIN_GENTZKOW_SPEECHES_PER_YEAR = 500
"""Floor for calling a Gentzkow overlap year usable.

The Senate produces tens of thousands of speech records a year in hein-daily,
so 500 is a tripwire for a truncated extract, not a volume model. It exists
because a truncated Gentzkow half fakes the C2 trap from the other side: it
makes GovInfo look uniformly LARGER, which is just as stable and just as
certifiable as the interrupted-GovInfo case.
"""


class OverlapIncompleteError(RuntimeError):
    """Raised when the overlap window is too thin to calibrate a verdict on."""


def compare_overlap(
    gentzkow_by_year: dict[int, int],
    govinfo_by_year: dict[int, int],
) -> dict:
    """Compare two china-mention series across their shared years."""
    years = sorted(set(gentzkow_by_year) & set(govinfo_by_year))
    if not years:
        raise ValueError("no overlapping years to calibrate on")

    zero_years = [y for y in years if not gentzkow_by_year[y]]
    if zero_years:
        # An inf ratio propagates into statistics.pstdev and surfaces as a bare
        # AttributeError that names neither the year nor the cause -- after
        # hours of downloading. Fail legibly instead.
        raise ValueError(
            f"gentzkow reports zero '{TERM}' mentions in {zero_years}, so the "
            "ratio for those years is undefined. A real Senate year is never "
            "silent on China, so this means the Gentzkow extract is truncated "
            "or mis-parsed for those years, not that the Senate said nothing."
        )

    per_year = []
    ratios = []
    rel_diffs = []
    for year in years:
        g = gentzkow_by_year[year]
        v = govinfo_by_year[year]
        ratio = v / g
        ratios.append(ratio)
        rel_diffs.append(abs(v - g) / g)
        per_year.append({"year": year, "gentzkow": g, "govinfo": v, "ratio": ratio})

    mean_ratio = statistics.fmean(ratios)
    stdev_ratio = statistics.pstdev(ratios)
    return {
        "years": years,
        "per_year": per_year,
        "mean_ratio": mean_ratio,
        "cv": stdev_ratio / mean_ratio if mean_ratio else float("inf"),
        "mean_rel_diff": statistics.fmean(rel_diffs),
    }


def choose_strategy(comparison: dict) -> str:
    """Pick the splice strategy the comparison supports.

    `concatenate` requires BOTH gates, not just agreement on the mean. Checking
    mean_rel_diff alone and returning early lets two offsetting outlier years
    cancel: measured on a 23-year overlap with one +50% and one -50% year,
    mean_rel_diff is 4.35% (inside the 5% tolerance) while cv is 14.7% (well
    outside the 10% stability bound). The mean says "these agree"; the spread
    says "these do not track each other". Without the conjunction the stability
    gate never runs and the halves are joined anyway.

    That failure lands exactly where it does the most damage. Beat 1's headline
    claim is that china mentions climb steeply after 2017, and 2017 IS the
    splice point, so a wrong `concatenate` manufactures a step change that
    cannot be told apart from the finding the notebook teaches.

    Requiring both changes no correct verdict: a genuinely close series still
    concatenates, a stable ratio still scales, an unstably diverging series
    still falls back to govinfo_only. Only the offsetting-outlier case moves,
    from concatenate to govinfo_only.
    """
    if comparison["mean_rel_diff"] <= AGREE_TOLERANCE and comparison["cv"] <= STABLE_CV:
        return "concatenate"
    if comparison["cv"] <= STABLE_CV:
        return "scale"
    return "govinfo_only"


def _govinfo_china_counts_by_year(
    raw_dir: Path, start_year: int, end_year: int
) -> tuple[dict[int, int], dict[str, int]]:
    """Count `china` mentions per year in the GovInfo raw cache.

    Walks via congress_cache.iter_govinfo_days, the one shared walker, so the
    verdict this module RECORDS and the splice build_congress_mentions APPLIES
    are computed from the same traversal. They previously came from two
    different implementations with different phantom filters and different
    error behaviour.

    A year only gets a key if its directory exists on disk, so a wholly
    missing year stays absent from the comparison rather than entering it as
    zero mentions.
    """
    skips: dict[str, int] = {}
    counts = {
        year: 0
        for year in range(start_year, end_year + 1)
        if (raw_dir / str(year)).is_dir()
    }
    for day in iter_govinfo_days(raw_dir, start_year, end_year, skips):
        for granule in day.granules:
            counts[day.year] += count_term(granule.get("text", ""), TERM)
    return counts, skips


def _gentzkow_china_counts_by_year(
    raw_dir: Path, start_year: int, end_year: int
) -> dict[int, int]:
    """Count `china` mentions per year in the Gentzkow raw cache.

    Reads data/_raw/congress_gentzkow/speeches_senate_{congress}.jsonl. Each
    record's `date` field (YYYYMMDD) determines its year rather than the
    congress number in the filename, since a single Congress can span two
    calendar years.
    """
    counts: dict[int, int] = {}
    for path in sorted(raw_dir.glob("speeches_senate_*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                date = record.get("date", "")
                if len(date) < 4 or not date[:4].isdigit():
                    continue
                year = int(date[:4])
                if year < start_year or year > end_year:
                    continue
                counts[year] = counts.get(year, 0) + count_term(
                    record.get("text", ""), TERM
                )
    return counts


def _gentzkow_speech_counts_by_year(
    raw_dir: Path, start_year: int, end_year: int
) -> dict[int, int]:
    """Speech records per year in the Gentzkow cache, every year in range.

    Counts RECORDS, not china mentions: this measures how much corpus is
    present, which is the question the completeness gate asks. A year with
    genuinely few china mentions is a finding; a year with almost no speeches
    at all is a truncated extract.
    """
    counts = {year: 0 for year in range(start_year, end_year + 1)}
    for path in sorted(raw_dir.glob("speeches_senate_*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                date = record.get("date", "")
                if len(date) < 4 or not date[:4].isdigit():
                    continue
                year = int(date[:4])
                if start_year <= year <= end_year:
                    counts[year] += 1
    return counts


def require_complete_overlap(
    gentzkow_dir: Path,
    govinfo_dir: Path,
    start_year: int = OVERLAP_START_YEAR,
    end_year: int = OVERLAP_END_YEAR,
) -> None:
    """Raise unless BOTH caches cover every overlap year at usable depth.

    This is C2's gate, and it has to live here rather than inside
    choose_strategy, because the statistics cannot see the problem. A
    uniformly partial cache yields a perfectly stable ratio -- cv 0.0000 --
    which is the signature choose_strategy reads as maximum confidence. The
    ratios really are stable; the counts really are what the cache contains.
    Only the cache itself knows it is incomplete.

    Presence is not completeness. A presence check passes a single leftover
    smoke-test day, and it also passes a uniformly partial download in which
    every year is present and every year is 2% fetched.

    Both sides are gated. An interrupted GovInfo fetch makes GovInfo look
    uniformly smaller; a truncated Gentzkow extract makes it look uniformly
    larger. Both are stable, both certify a `scale` join, and `scale` is the
    one branch that actively rewrites the numbers -- so both manufacture a
    step change at exactly 2017, which is exactly where Beat 1's headline
    finding lives.
    """
    problems = []
    years = [y for y in CALIBRATION_YEARS if start_year <= y <= end_year]

    _, bad_govinfo = govinfo_years_usable(govinfo_dir, years)
    if bad_govinfo:
        report = coverage_report(govinfo_dir, min(years), max(years))
        detail = "\n".join(f"      {report[y].describe()}" for y in bad_govinfo)
        problems.append(
            f"  - GovInfo: {len(bad_govinfo)} of {len(years)} calibration "
            f"year(s) not fully covered against their sitemap manifest:\n{detail}"
        )

    all_gentzkow = _gentzkow_speech_counts_by_year(gentzkow_dir, start_year, end_year)
    gentzkow_counts = {y: all_gentzkow[y] for y in years}
    bad_gentzkow = sorted(
        y for y, n in gentzkow_counts.items() if n < MIN_GENTZKOW_SPEECHES_PER_YEAR
    )
    if bad_gentzkow:
        detail = ", ".join(f"{y} ({gentzkow_counts[y]} speech(es))" for y in bad_gentzkow)
        problems.append(
            f"  - Gentzkow: {len(bad_gentzkow)} of {len(years)} calibration year(s) below "
            f"{MIN_GENTZKOW_SPEECHES_PER_YEAR} speech records: {detail}"
        )

    if problems:
        raise OverlapIncompleteError(
            f"The {start_year}-{end_year} overlap is too thin to calibrate a "
            "splice verdict on:\n" + "\n".join(problems) + "\n\n"
            "This is not a warning. A partially-fetched overlap yields a "
            "PERFECTLY STABLE ratio (cv 0.0000), which choose_strategy reads "
            "as maximum confidence and certifies as a `scale` join -- and "
            "`scale` rewrites every pre-2017 count, manufacturing a step "
            "change at exactly 2017 that is indistinguishable from the "
            "notebook's headline finding.\n"
            "Re-run the fetch script(s) to completion. Do not lower the "
            "floors to get past this."
        )


def resolve_strategy(
    gentzkow_dir: Path = CONGRESS_RAW_GENTZKOW,
    govinfo_dir: Path = CONGRESS_RAW_GOVINFO,
) -> tuple[str, dict]:
    """The splice verdict, gated on overlap completeness. Returns (strategy, comparison).

    The one entry point every build uses, so that three builds cannot drift on
    how the verdict is derived -- the same anti-drift argument that put the
    tokenizer and the cache walker in shared modules. Raises
    OverlapIncompleteError before computing anything if the overlap is too thin
    to calibrate on.
    """
    require_complete_overlap(gentzkow_dir, govinfo_dir)
    gentzkow_all = _gentzkow_china_counts_by_year(
        gentzkow_dir, OVERLAP_START_YEAR, OVERLAP_END_YEAR
    )
    govinfo_all, _ = _govinfo_china_counts_by_year(
        govinfo_dir, OVERLAP_START_YEAR, OVERLAP_END_YEAR
    )
    # Restrict BOTH sides to CALIBRATION_YEARS. Gentzkow has every year (it is
    # a bulk archive), so without this the intersection would silently be
    # whatever GovInfo years happen to be on disk -- which is exactly the
    # "verdict computed on an unstated subset" failure the coverage gate
    # exists to prevent.
    gentzkow_by_year = {y: gentzkow_all[y] for y in CALIBRATION_YEARS if y in gentzkow_all}
    govinfo_by_year = {y: govinfo_all[y] for y in CALIBRATION_YEARS if y in govinfo_all}
    comparison = compare_overlap(gentzkow_by_year, govinfo_by_year)
    return choose_strategy(comparison), comparison


def govinfo_only_message(consumer: str, consequence: str) -> str:
    """The shared text for refusing to build under a `govinfo_only` verdict."""
    return (
        "calibrate_splice.choose_strategy returned 'govinfo_only': the "
        "Gentzkow and GovInfo china series diverge unstably over "
        f"{OVERLAP_START_YEAR}-{OVERLAP_END_YEAR}, so the two halves must not "
        f"be joined. {consequence} That is a decision for Heagen, not "
        f"something {consumer} will apply silently. STOP and resolve this "
        "before re-running the build."
    )


def main() -> int:
    missing = []
    if not CONGRESS_RAW_GENTZKOW.exists() or not any(
        CONGRESS_RAW_GENTZKOW.glob("speeches_senate_*.jsonl")
    ):
        missing.append(
            f"  - Gentzkow cache missing or empty: {CONGRESS_RAW_GENTZKOW}\n"
            "    Produce it with: python scripts/fetch_congress_gentzkow.py"
        )
    if not CONGRESS_RAW_GOVINFO.exists():
        missing.append(
            f"  - GovInfo cache missing or empty for {OVERLAP_START_YEAR}-"
            f"{OVERLAP_END_YEAR}: {CONGRESS_RAW_GOVINFO}\n"
            "    Produce it with: python scripts/fetch_congress_govinfo.py "
            f"--start-year {OVERLAP_START_YEAR} --end-year 2024"
        )
    if missing:
        print(
            "Cannot run the splice calibration: required raw cache(s) are "
            "absent.\n" + "\n".join(missing) + "\n\n"
            "These are long-running downloads (the GovInfo pull is roughly "
            "110k requests; the Gentzkow archive is 11.4 GB) and are not "
            "run automatically. See the scripts above for what each one "
            "produces and where."
        )
        return 1

    try:
        require_complete_overlap(CONGRESS_RAW_GENTZKOW, CONGRESS_RAW_GOVINFO)
    except OverlapIncompleteError as exc:
        print(f"Cannot run the splice calibration.\n\n{exc}")
        return 1

    print(
        f"Counting '{TERM}' mentions per year, "
        f"{OVERLAP_START_YEAR}-{OVERLAP_END_YEAR}..."
    )
    gentzkow_by_year = _gentzkow_china_counts_by_year(
        CONGRESS_RAW_GENTZKOW, OVERLAP_START_YEAR, OVERLAP_END_YEAR
    )
    govinfo_by_year, govinfo_skips = _govinfo_china_counts_by_year(
        CONGRESS_RAW_GOVINFO, OVERLAP_START_YEAR, OVERLAP_END_YEAR
    )
    if govinfo_skips:
        print(
            "GovInfo cache skipped: "
            + ", ".join(f"{n} {reason}" for reason, n in sorted(govinfo_skips.items()))
        )

    comparison = compare_overlap(gentzkow_by_year, govinfo_by_year)
    strategy = choose_strategy(comparison)

    print(f"{'year':>6}  {'gentzkow':>10}  {'govinfo':>10}  {'ratio':>8}")
    for row in comparison["per_year"]:
        print(
            f"{row['year']:>6}  {row['gentzkow']:>10}  {row['govinfo']:>10}  "
            f"{row['ratio']:>8.3f}"
        )
    print()
    print(f"mean_rel_diff: {comparison['mean_rel_diff']:.4f}")
    print(f"mean_ratio:    {comparison['mean_ratio']:.4f}")
    print(f"cv:            {comparison['cv']:.4f}")
    print(f"STRATEGY:      {strategy}")
    if strategy == "govinfo_only":
        print(
            "\ngovinfo_only means the splice is abandoned: 1990-1993 is "
            "dropped, the mentions build's year range changes, and the "
            "Japan beat must be re-anchored to the 1994-2000 decline. "
            "STOP and tell Heagen before continuing."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
