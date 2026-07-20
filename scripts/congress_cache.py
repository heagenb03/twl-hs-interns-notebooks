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
congress_companions.csv. `govinfo_range_usable` requires every year in the
range to clear a real-day floor instead.

It cannot live in build_congress_mentions.py: calibrate_splice would import it
and build_congress_mentions already imports calibrate_splice.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, NamedTuple

MIN_REAL_DAYS_PER_YEAR = 20
"""Floor for calling a cached year usable.

The Senate sits well over 100 days in a normal year, so 20 is deliberately
loose -- it is a tripwire for an interrupted or never-started fetch, not an
attendance model. It must never be 0: that would make every range usable,
including an empty cache.
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


def govinfo_range_usable(
    raw_dir: Path,
    start_year: int,
    end_year: int,
    min_days: int = MIN_REAL_DAYS_PER_YEAR,
) -> tuple[bool, list[int]]:
    """True only if EVERY year in the range clears `min_days` real cached days.

    This is the completeness check, as distinct from a presence check. Presence
    is satisfied by a single day anywhere in the range -- which is how a
    leftover 2023 smoke-test directory passed as an eight-year corpus. An
    interrupted fetch does not fail uniformly either: it stops partway through
    one year, so the gate has to be per-year rather than over the range.

    Returns (usable, sorted list of years that are missing or short).
    """
    counts = real_day_counts(raw_dir, start_year, end_year)
    bad_years = sorted(year for year, n in counts.items() if n < min_days)
    return not bad_years, bad_years
