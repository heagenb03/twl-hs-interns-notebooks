# scripts/congress_cache.py
"""The one walker over the raw GovInfo CREC cache.

Four independent walkers grew across Tasks 7-10 -- one each in
calibrate_splice, build_congress_mentions, build_congress_companions and
build_congress_senators. They disagreed on two things:

  * phantom-marker filtering. Two filtered by filename (`*.phantom.json`), two
    by the absence of a "granules" key. The key-based filter is correct: it
    survives a change to the marker naming convention in
    fetch_congress_govinfo.py, which the filename filter does not.
  * error handling. One crashed on a malformed day file, one counted it and
    continued, one continued with no counter at all. Count-and-continue wins:
    a single truncated day must not abort a walk over eight years of cache,
    and this project's counting-discipline rule says dropped data is always
    reported.

That divergence carried no wrong-count risk today, but it meant the
human-facing splice verdict (calibrate_splice) and the applied splice
(build_congress_mentions) came from two different implementations of one
concept -- the exact drift that sharing congress_tokenize exists to prevent.

This module also owns the difference between a cache being PRESENT and a cache
being COMPLETE. `_govinfo_years_present`-style checks are satisfied by one
leftover smoke-test day, which is how build_congress_companions came to accept
a single day of Senate business as a corpus and write a validator-clean
congress_companions.csv.

Completeness is measured against a per-year MANIFEST the fetcher writes from
the sitemap, not against a flat day floor. A flat floor answers "did the fetch
start for this year", which is the wrong question for the splice calibration:
there, the ratio between the two corpora is directly proportional to how much
of each was downloaded, so a uniformly partial cache produces a perfectly
stable ratio and certifies a bogus `scale` join. Only the sitemap knows how
many days a year should hold, and the manifest is how that number reaches an
offline build without putting a network call inside it.

It cannot live in build_congress_mentions.py: calibrate_splice would import it
and build_congress_mentions already imports calibrate_splice.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator, NamedTuple

MIN_REAL_DAYS_PER_YEAR = 20
"""Floor for calling a cached year usable.

The Senate sits well over 100 days in a normal year, so 20 is deliberately
loose -- it is a tripwire for an interrupted or never-started fetch, not an
attendance model. It must never be 0: that would make every range usable,
including an empty cache.
"""

MAX_PHANTOM_SHARE = 0.10
"""Ceiling on the fraction of a year's expected days that may be phantoms.

The only measured real-world rate is ~1.4% (2023: 3 of 209 days). This mirrors
fetch_congress_govinfo's own sanity threshold so that a year cannot be declared
complete on markers alone.
"""

PHANTOM_SKIP = "phantom_marker"
BAD_JSON_SKIP = "bad_json"


class GovInfoDay(NamedTuple):
    """One cached CREC day, already parsed and known to carry granules."""

    year: int
    package: str
    path: Path
    granules: list[dict]


def _is_real_day(payload: object) -> bool:
    """A phantom marker records a package that never existed; it has no granules.

    Checked by KEY, not by filename. fetch_congress_govinfo.py currently writes
    markers as `{pkg}.phantom.json`, but a naive `*.json` glob picks them up and
    a filename filter breaks silently the day that convention changes.
    """
    return isinstance(payload, dict) and "granules" in payload


def iter_govinfo_days(
    raw_dir: Path,
    start_year: int,
    end_year: int,
    skips: dict[str, int] | None = None,
) -> Iterator[GovInfoDay]:
    """Yield every real cached day in [start_year, end_year], in page order.

    Days are yielded in sorted filename order within a year, and years in
    ascending order. Order is load-bearing: build_congress_senators threads
    `carry_in` across granules in page order, so an unstable walk silently
    re-attributes continuation text to the wrong senator.

    `skips`, if given, is incremented in place by reason -- 'phantom_marker'
    for a payload with no "granules" key, 'bad_json' for a day file that
    failed to parse. Callers own the reporting; this function never prints and
    never swallows a skip uncounted.
    """
    for year in range(start_year, end_year + 1):
        year_dir = raw_dir / str(year)
        if not year_dir.is_dir():
            continue
        for path in sorted(year_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                if skips is not None:
                    skips[BAD_JSON_SKIP] = skips.get(BAD_JSON_SKIP, 0) + 1
                continue
            if not _is_real_day(payload):
                if skips is not None:
                    skips[PHANTOM_SKIP] = skips.get(PHANTOM_SKIP, 0) + 1
                continue
            yield GovInfoDay(
                year=year,
                package=payload.get("package", path.stem),
                path=path,
                granules=payload["granules"],
            )


def real_day_counts(raw_dir: Path, start_year: int, end_year: int) -> dict[int, int]:
    """Real (non-phantom, parseable) cached days per year, every year in range.

    Every year in the range gets a key, including years with no directory at
    all, so a caller reporting coverage names the missing years rather than
    leaving them out of its own report.
    """
    counts = {year: 0 for year in range(start_year, end_year + 1)}
    for day in iter_govinfo_days(raw_dir, start_year, end_year):
        counts[day.year] += 1
    return counts


def phantom_counts(raw_dir: Path, start_year: int, end_year: int) -> dict[int, int]:
    """Committed phantom markers per year -- days GovInfo proves do not exist.

    A phantom day is genuinely absent from GovInfo, not missing from our cache,
    so it counts toward a year being fully accounted for. fetch_congress_govinfo
    only commits markers once the year clears its own sanity gate, so a marker
    on disk is a believable claim rather than an outage artifact.
    """
    counts = {year: 0 for year in range(start_year, end_year + 1)}
    for year in range(start_year, end_year + 1):
        year_dir = raw_dir / str(year)
        if year_dir.is_dir():
            counts[year] = len(list(year_dir.glob("*.phantom.json")))
    return counts


# --- manifests: what a complete year is supposed to contain -----------------

MANIFEST_DIR_NAME = "_manifests"
"""Manifests live OUTSIDE the per-year directories on purpose.

A manifest inside `{year}/` would be picked up by the `*.json` glob and counted
as a phantom marker, inflating the very number the coverage check reads.
"""


def manifest_path(raw_dir: Path, year: int) -> Path:
    return raw_dir / MANIFEST_DIR_NAME / f"{year}.json"


def write_manifest(raw_dir: Path, year: int, expected_packages: list[str]) -> None:
    """Record how many CREC days `year` is supposed to have.

    Written by fetch_congress_govinfo as soon as the sitemap resolves and
    clears its floor -- BEFORE any day is downloaded. That ordering is the
    point: an interrupted year then leaves a manifest saying 150 next to 40
    cached days, which is exactly the discrepancy the coverage gate exists to
    see. A manifest written at the END would be absent after an interruption,
    and absence is indistinguishable from "never started".
    """
    path = manifest_path(raw_dir, year)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(
            {
                "year": year,
                "expected_days": len(expected_packages),
                "packages": sorted(expected_packages),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    tmp.replace(path)


def read_manifest(raw_dir: Path, year: int) -> dict | None:
    """The year's manifest, or None if it was never written or is unreadable."""
    path = manifest_path(raw_dir, year)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) and "expected_days" in payload else None


class YearCoverage(NamedTuple):
    """How much of a year is actually on disk, against how much should be."""

    year: int
    expected: int | None  # None when no manifest was ever written
    fetched: int
    phantom: int

    @property
    def accounted(self) -> int:
        """Days resolved either way: downloaded, or proven not to exist."""
        return self.fetched + self.phantom

    @property
    def complete(self) -> bool:
        if self.expected is None:
            return False
        if self.expected < MIN_REAL_DAYS_PER_YEAR:
            # A manifest claiming a handful of days for a full Senate year is
            # itself the symptom -- the sitemap served an error page. Believing
            # it would let a 3-day year certify as "fully covered".
            return False
        if self.phantom > self.expected * MAX_PHANTOM_SHARE:
            # Without this, phantoms alone satisfy the manifest and a year that
            # 404'd on every single request certifies as fully covered.
            # fetch_congress_govinfo's own rate gate should abort long before
            # committing markers at this density, but the build side must not
            # depend on the fetch side having been the one to notice.
            return False
        return self.accounted >= self.expected

    def describe(self) -> str:
        if self.expected is None:
            return f"{self.year}: no manifest (fetch never ran for this year)"
        return (
            f"{self.year}: {self.accounted}/{self.expected} days accounted "
            f"({self.fetched} fetched + {self.phantom} phantom)"
        )


def coverage_report(
    raw_dir: Path, start_year: int, end_year: int
) -> dict[int, YearCoverage]:
    """Per-year coverage against each year's manifest."""
    fetched = real_day_counts(raw_dir, start_year, end_year)
    phantom = phantom_counts(raw_dir, start_year, end_year)
    report = {}
    for year in range(start_year, end_year + 1):
        manifest = read_manifest(raw_dir, year)
        report[year] = YearCoverage(
            year=year,
            expected=manifest["expected_days"] if manifest else None,
            fetched=fetched[year],
            phantom=phantom[year],
        )
    return report


def govinfo_years_usable(
    raw_dir: Path, years: Iterable[int]
) -> tuple[bool, list[int]]:
    """Same check as govinfo_range_usable, over an explicit, possibly sparse set.

    The splice calibration does not need every year of the overlap -- pulling
    1994-2016 in full costs ~32 hours and none of it reaches a published CSV.
    It samples instead (see calibrate_splice.CALIBRATION_YEARS), so its gate
    has to ask about a set of years rather than a contiguous span. Years NOT in
    the set are not checked and their absence is not a failure; every year that
    IS in the set must be fully covered, exactly as in the contiguous case.
    """
    years = sorted(set(years))
    if not years:
        return True, []
    report = coverage_report(raw_dir, min(years), max(years))
    bad_years = [y for y in years if not report[y].complete]
    return not bad_years, bad_years


def govinfo_range_usable(
    raw_dir: Path, start_year: int, end_year: int
) -> tuple[bool, list[int]]:
    """True only if EVERY year in the range is fully accounted for.

    Coverage, not presence, and not a flat day floor either. A flat floor is a
    "did the fetch start" tripwire: it is fine for a build that just wants less
    data, but it is useless for the splice calibration, where the ratio between
    the two corpora is directly proportional to how much of each was
    downloaded. Measured: a GovInfo overlap fetched uniformly at 25 days/year
    (a real Senate year runs ~150) clears a 20-day floor while its china counts
    are a fraction of a percent of a complete Gentzkow half -- mean_ratio
    0.00125, cv 0.00000, verdict `scale`. The gate does not merely fail to
    fire; it certifies an 800x step at exactly 2017 with maximum confidence.

    The only thing that knows how much a year should hold is the sitemap, so
    the fetcher records it in a manifest and this gate reads it back. That
    keeps build() a pure offline transform -- no network call -- while still
    measuring against truth rather than a guess.

    Returns (usable, sorted list of years that are missing, short, or
    unmanifested).
    """
    report = coverage_report(raw_dir, start_year, end_year)
    bad_years = sorted(year for year, cov in report.items() if not cov.complete)
    return not bad_years, bad_years
