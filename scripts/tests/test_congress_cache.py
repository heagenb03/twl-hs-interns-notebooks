# scripts/tests/test_congress_cache.py
"""Tests for the single shared GovInfo cache walker.

Before this module existed there were FOUR independent walkers
(calibrate_splice._govinfo_china_counts_by_year,
build_congress_mentions.govinfo_counts_by_year,
build_congress_companions.govinfo_segments_by_era,
build_congress_senators.govinfo_bioguide_roster) using three different
phantom-marker filters and three different error behaviours. The human-facing
splice verdict and the applied splice therefore came from two different
implementations of one concept -- exactly the drift that sharing
congress_tokenize exists to prevent.
"""
import json

import pytest

from congress_cache import (
    MIN_REAL_DAYS_PER_YEAR,
    govinfo_range_usable,
    iter_govinfo_days,
    real_day_counts,
)


def _write_day(root, year, pkg, granules):
    year_dir = root / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    (year_dir / f"{pkg}.json").write_text(
        json.dumps({"package": pkg, "granules": granules}), encoding="utf-8"
    )


def _write_phantom(root, year, pkg):
    year_dir = root / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    (year_dir / f"{pkg}.phantom.json").write_text(
        json.dumps({"package": pkg, "reason": "not found"}), encoding="utf-8"
    )


def _drain(root, start, end):
    skips = {}
    days = list(iter_govinfo_days(root, start, end, skips))
    return days, skips


def test_yields_every_real_day_in_range(tmp_path):
    _write_day(tmp_path, 2018, "CREC-2018-01-03", [{"text": "china"}])
    _write_day(tmp_path, 2019, "CREC-2019-01-03", [{"text": "trade"}])
    days, skips = _drain(tmp_path, 2018, 2019)
    assert [d.year for d in days] == [2018, 2019]
    assert sum(skips.values()) == 0


def test_years_outside_the_requested_range_are_not_walked(tmp_path):
    _write_day(tmp_path, 2016, "CREC-2016-01-03", [{"text": "china"}])
    _write_day(tmp_path, 2018, "CREC-2018-01-03", [{"text": "china"}])
    days, _ = _drain(tmp_path, 2017, 2024)
    assert [d.year for d in days] == [2018]


def test_phantom_markers_are_filtered_by_key_not_filename(tmp_path):
    """A marker renamed away from *.phantom.json must still be excluded.

    calibrate_splice filtered by filename; build_congress_mentions filtered by
    the "granules" key. The key-based filter is the correct one: it survives a
    change to the marker naming convention in fetch_congress_govinfo.py.
    """
    year_dir = tmp_path / "2018"
    year_dir.mkdir(parents=True)
    (year_dir / "CREC-2018-01-03.missing.json").write_text(
        json.dumps({"package": "CREC-2018-01-03", "reason": "not found"}),
        encoding="utf-8",
    )
    days, skips = _drain(tmp_path, 2018, 2018)
    assert days == []
    assert skips["phantom_marker"] == 1


def test_malformed_day_is_counted_and_does_not_crash(tmp_path):
    """calibrate_splice's walker had no try/except and CRASHED on this input,
    while build_congress_mentions' walker counted it and continued. One
    behaviour must win, and it is count-and-continue -- a single truncated day
    file must not abort a walk over eight years of cache."""
    year_dir = tmp_path / "2018"
    year_dir.mkdir(parents=True)
    (year_dir / "CREC-2018-01-03.json").write_text("{not json", encoding="utf-8")
    _write_day(tmp_path, 2018, "CREC-2018-01-04", [{"text": "china"}])
    days, skips = _drain(tmp_path, 2018, 2018)
    assert [d.package for d in days] == ["CREC-2018-01-04"]
    assert skips["bad_json"] == 1


def test_every_skip_is_counted_never_silent(tmp_path):
    """The counting-discipline rule: dropped data is reported, never dropped."""
    _write_phantom(tmp_path, 2018, "CREC-2018-01-01")
    year_dir = tmp_path / "2018"
    (year_dir / "CREC-2018-01-02.json").write_text("{bad", encoding="utf-8")
    _write_day(tmp_path, 2018, "CREC-2018-01-03", [{"text": "china"}])
    days, skips = _drain(tmp_path, 2018, 2018)
    assert len(days) == 1
    assert skips == {"bad_json": 1, "phantom_marker": 1}


def test_days_are_walked_in_stable_page_order(tmp_path):
    """build_congress_senators threads carry_in across granules in page order,
    so an unstable walk order silently re-attributes continuation text."""
    for pkg in ["CREC-2018-01-05", "CREC-2018-01-03", "CREC-2018-01-04"]:
        _write_day(tmp_path, 2018, pkg, [{"text": "china"}])
    days, _ = _drain(tmp_path, 2018, 2018)
    assert [d.package for d in days] == [
        "CREC-2018-01-03",
        "CREC-2018-01-04",
        "CREC-2018-01-05",
    ]


# --- completeness, not presence -------------------------------------------


def test_one_cached_day_is_not_a_usable_year(tmp_path):
    """C1. build_congress_companions._govinfo_years_present returned True for a
    single leftover smoke-test day and build() then wrote a validator-clean
    40-row congress_companions.csv whose 2020s row was one day of Senate
    business: nato, state, all, one, richard, whereas, united, states,
    hezbollah, washington. That is Beat 2's entire 2020s teaching claim."""
    _write_day(tmp_path, 2023, "CREC-2023-06-14", [{"text": "china"}])
    usable, bad_years = govinfo_range_usable(tmp_path, 2017, 2024)
    assert usable is False
    assert 2023 in bad_years


def test_range_is_usable_only_when_every_year_clears_the_floor(tmp_path):
    for year in range(2017, 2025):
        for i in range(MIN_REAL_DAYS_PER_YEAR):
            _write_day(tmp_path, year, f"CREC-{year}-{i:03d}", [{"text": "china"}])
    usable, bad_years = govinfo_range_usable(tmp_path, 2017, 2024)
    assert usable is True
    assert bad_years == []


def test_a_single_short_year_fails_the_whole_range(tmp_path):
    """An interrupted fetch is the likeliest outcome of a 110k-request job, and
    it does not fail uniformly -- it stops partway through one year."""
    for year in range(2017, 2025):
        n = MIN_REAL_DAYS_PER_YEAR if year != 2021 else MIN_REAL_DAYS_PER_YEAR - 1
        for i in range(n):
            _write_day(tmp_path, year, f"CREC-{year}-{i:03d}", [{"text": "china"}])
    usable, bad_years = govinfo_range_usable(tmp_path, 2017, 2024)
    assert usable is False
    assert bad_years == [2021]


def test_missing_year_directory_is_a_bad_year(tmp_path):
    for i in range(MIN_REAL_DAYS_PER_YEAR):
        _write_day(tmp_path, 2017, f"CREC-2017-{i:03d}", [{"text": "china"}])
    usable, bad_years = govinfo_range_usable(tmp_path, 2017, 2018)
    assert usable is False
    assert bad_years == [2018]


def test_phantom_markers_do_not_count_toward_the_real_day_floor(tmp_path):
    """A year that 404'd every day would otherwise look complete."""
    for i in range(MIN_REAL_DAYS_PER_YEAR):
        _write_phantom(tmp_path, 2017, f"CREC-2017-{i:03d}")
    usable, bad_years = govinfo_range_usable(tmp_path, 2017, 2017)
    assert usable is False
    assert bad_years == [2017]
    assert real_day_counts(tmp_path, 2017, 2017) == {2017: 0}


def test_real_day_counts_reports_every_year_in_range(tmp_path):
    _write_day(tmp_path, 2018, "CREC-2018-01-03", [{"text": "china"}])
    _write_phantom(tmp_path, 2018, "CREC-2018-01-04")
    assert real_day_counts(tmp_path, 2017, 2019) == {2017: 0, 2018: 1, 2019: 0}


def test_caller_may_override_the_floor(tmp_path):
    _write_day(tmp_path, 2017, "CREC-2017-01-03", [{"text": "china"}])
    assert govinfo_range_usable(tmp_path, 2017, 2017, min_days=1) == (True, [])
    assert govinfo_range_usable(tmp_path, 2017, 2017, min_days=2) == (False, [2017])


def test_min_days_floor_is_not_silently_zero():
    """min_days=0 would make every range usable, including an empty cache."""
    assert MIN_REAL_DAYS_PER_YEAR >= 20
