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

from congress_tokenize import count_term
from twl_common import CONGRESS_RAW_GENTZKOW, CONGRESS_RAW_GOVINFO

AGREE_TOLERANCE = 0.05   # mean |relative difference| under 5% -> concatenate
STABLE_CV = 0.10         # coefficient of variation of the ratio under 10% -> scale

OVERLAP_START_YEAR = 1994
OVERLAP_END_YEAR = 2016  # inclusive
TERM = "china"


def compare_overlap(
    gentzkow_by_year: dict[int, int],
    govinfo_by_year: dict[int, int],
) -> dict:
    """Compare two china-mention series across their shared years."""
    years = sorted(set(gentzkow_by_year) & set(govinfo_by_year))
    if not years:
        raise ValueError("no overlapping years to calibrate on")

    per_year = []
    ratios = []
    rel_diffs = []
    for year in years:
        g = gentzkow_by_year[year]
        v = govinfo_by_year[year]
        ratio = v / g if g else float("inf")
        ratios.append(ratio)
        rel_diffs.append(abs(v - g) / g if g else float("inf"))
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
) -> dict[int, int]:
    """Count `china` mentions per year in the GovInfo raw cache.

    Reads data/_raw/congress_govinfo/{year}/{package}.json. Each year's
    directory also holds `{package}.phantom.json` marker files recording
    packages that never existed (see fetch_congress_govinfo.py); those have
    no "granules" key and must be excluded from a naive `*.json` glob.
    """
    counts: dict[int, int] = {}
    for year in range(start_year, end_year + 1):
        year_dir = raw_dir / str(year)
        if not year_dir.is_dir():
            continue
        total = 0
        for path in sorted(year_dir.glob("*.json")):
            if path.name.endswith(".phantom.json"):
                continue
            day = json.loads(path.read_text(encoding="utf-8"))
            for granule in day.get("granules", []):
                total += count_term(granule.get("text", ""), TERM)
        counts[year] = total
    return counts


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


def _govinfo_overlap_years_present(raw_dir: Path, start_year: int, end_year: int) -> bool:
    """True if at least one non-phantom day exists for a year in the overlap.

    A bare `any(raw_dir.iterdir())` would be satisfied by an unrelated
    partial cache (e.g. a 2023-only download) that has nothing in the
    1994-2016 overlap window this calibration actually needs.
    """
    for year in range(start_year, end_year + 1):
        year_dir = raw_dir / str(year)
        if not year_dir.is_dir():
            continue
        if any(
            p for p in year_dir.glob("*.json") if not p.name.endswith(".phantom.json")
        ):
            return True
    return False


def main() -> int:
    missing = []
    if not CONGRESS_RAW_GENTZKOW.exists() or not any(
        CONGRESS_RAW_GENTZKOW.glob("speeches_senate_*.jsonl")
    ):
        missing.append(
            f"  - Gentzkow cache missing or empty: {CONGRESS_RAW_GENTZKOW}\n"
            "    Produce it with: python scripts/fetch_congress_gentzkow.py"
        )
    if not CONGRESS_RAW_GOVINFO.exists() or not _govinfo_overlap_years_present(
        CONGRESS_RAW_GOVINFO, OVERLAP_START_YEAR, OVERLAP_END_YEAR
    ):
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

    print(
        f"Counting '{TERM}' mentions per year, "
        f"{OVERLAP_START_YEAR}-{OVERLAP_END_YEAR}..."
    )
    gentzkow_by_year = _gentzkow_china_counts_by_year(
        CONGRESS_RAW_GENTZKOW, OVERLAP_START_YEAR, OVERLAP_END_YEAR
    )
    govinfo_by_year = _govinfo_china_counts_by_year(
        CONGRESS_RAW_GOVINFO, OVERLAP_START_YEAR, OVERLAP_END_YEAR
    )

    comparison = compare_overlap(gentzkow_by_year, govinfo_by_year)
    strategy = choose_strategy(comparison)

    expected_years = OVERLAP_END_YEAR - OVERLAP_START_YEAR + 1
    if len(comparison["years"]) < expected_years:
        print(
            f"WARNING: only {len(comparison['years'])}/{expected_years} overlap "
            "years have data in both caches. The verdict below is calibrated on "
            "a partial overlap, not the full 1994-2016 window -- this usually "
            "means a fetch was interrupted. Re-run the fetch script(s) to "
            "completion before trusting this verdict."
        )

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
