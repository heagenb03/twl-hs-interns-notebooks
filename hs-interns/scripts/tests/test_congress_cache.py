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
    coverage_report,
    govinfo_range_usable,
    iter_govinfo_days,
    read_manifest,
    real_day_counts,
    write_manifest,
)

SESSION_DAYS = 30  # stands in for a full Senate year (~150); kept small for test speed


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


def _fetch_year(root, year, expected=SESSION_DAYS, fetched=None, phantom=0):
    """Simulate a fetch: manifest written first, then some days land."""
    packages = [f"CREC-{year}-{i:03d}" for i in range(expected)]
    write_manifest(root, year, packages)
    fetched = expected - phantom if fetched is None else fetched
    for pkg in packages[:fetched]:
        _write_day(root, year, pkg, [{"text": "china"}])
    for pkg in packages[fetched:fetched + phantom]:
        _write_phantom(root, year, pkg)


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


def test_a_fully_fetched_range_is_usable(tmp_path):
    for year in range(2017, 2025):
        _fetch_year(tmp_path, year)
    assert govinfo_range_usable(tmp_path, 2017, 2024) == (True, [])


def test_a_year_fetched_well_above_a_flat_floor_but_far_short_of_its_manifest_fails(
    tmp_path,
):
    """THE KILL ZONE. This is the case a flat MIN_REAL_DAYS_PER_YEAR floor let
    through, and it is the one that actually ships a wrong headline finding.

    The fixture is scaled down for speed (SESSION_DAYS stands in for ~150), but
    the shape is the measured one: at 25 real days against a full Senate year,
    a flat 20-day tripwire passes while the china counts are a fraction of a
    percent of a complete Gentzkow half -- mean_ratio 0.00125, cv 0.00000. So
    choose_strategy does not merely fail to reject it, it CERTIFIES a `scale`
    join with maximum confidence and manufactures an 800x step at exactly 2017,
    which is exactly where Beat 1's headline claim lives.

    Only the manifest can see this. Nothing about the cached days themselves
    looks wrong; the discrepancy is between what is on disk and what the
    sitemap said should be.
    """
    _fetch_year(tmp_path, 2017, expected=SESSION_DAYS, fetched=25)
    usable, bad_years = govinfo_range_usable(tmp_path, 2017, 2017)
    assert usable is False
    assert bad_years == [2017]
    assert 25 > MIN_REAL_DAYS_PER_YEAR, "fixture no longer exercises the kill zone"


def test_a_uniformly_partial_range_fails_every_year(tmp_path):
    """An interrupted bulk pull is uniform, which is what makes it dangerous."""
    for year in range(2017, 2025):
        _fetch_year(tmp_path, year, expected=SESSION_DAYS, fetched=25)
    usable, bad_years = govinfo_range_usable(tmp_path, 2017, 2024)
    assert usable is False
    assert bad_years == list(range(2017, 2025))


def test_a_single_short_year_fails_the_whole_range(tmp_path):
    for year in range(2017, 2025):
        _fetch_year(tmp_path, year, fetched=SESSION_DAYS if year != 2021 else 28)
    assert govinfo_range_usable(tmp_path, 2017, 2024) == (False, [2021])


def test_phantom_days_count_as_accounted_for(tmp_path):
    """A phantom day is absent from GovInfo, not missing from our cache. The
    real 2023 rate is ~1.4%, so treating phantoms as a shortfall would make
    every year permanently incomplete."""
    _fetch_year(tmp_path, 2017, expected=SESSION_DAYS, fetched=28, phantom=2)
    assert govinfo_range_usable(tmp_path, 2017, 2017) == (True, [])


def test_an_all_phantom_year_is_not_complete(tmp_path):
    """The opposite pressure: if phantoms alone could satisfy a manifest, a
    year that 404'd on every request would certify as fully covered."""
    _fetch_year(tmp_path, 2017, expected=SESSION_DAYS, fetched=0, phantom=SESSION_DAYS)
    usable, bad_years = govinfo_range_usable(tmp_path, 2017, 2017)
    assert usable is False
    assert bad_years == [2017]


def test_a_year_with_no_manifest_is_never_complete(tmp_path):
    """No manifest means nothing knows how much this year should hold. That is
    a refusal, not a pass -- the pre-manifest cache in this worktree must not
    silently certify."""
    for i in range(SESSION_DAYS):
        _write_day(tmp_path, 2017, f"CREC-2017-{i:03d}", [{"text": "china"}])
    assert govinfo_range_usable(tmp_path, 2017, 2017) == (False, [2017])


def test_an_implausibly_small_manifest_is_not_believed(tmp_path):
    """A manifest claiming 3 days for a full Senate year is itself the symptom
    -- the sitemap served an error page. Believing it lets a 3-day year
    certify as fully covered."""
    _fetch_year(tmp_path, 2017, expected=3)
    assert govinfo_range_usable(tmp_path, 2017, 2017) == (False, [2017])


def test_missing_year_directory_is_a_bad_year(tmp_path):
    _fetch_year(tmp_path, 2017)
    assert govinfo_range_usable(tmp_path, 2017, 2018) == (False, [2018])


def test_the_manifest_lives_outside_the_year_directories(tmp_path):
    """A manifest inside {year}/ would be swept up by the *.json glob and
    counted as a phantom marker -- inflating the very number the coverage
    check reads."""
    _fetch_year(tmp_path, 2017, expected=SESSION_DAYS, fetched=SESSION_DAYS)
    assert real_day_counts(tmp_path, 2017, 2017) == {2017: SESSION_DAYS}
    _, skips = _drain(tmp_path, 2017, 2017)
    assert skips == {}


def test_manifest_roundtrips(tmp_path):
    write_manifest(tmp_path, 2017, ["CREC-2017-b", "CREC-2017-a"])
    manifest = read_manifest(tmp_path, 2017)
    assert manifest["expected_days"] == 2
    assert manifest["packages"] == ["CREC-2017-a", "CREC-2017-b"]


def test_a_corrupt_manifest_reads_as_absent_not_as_zero(tmp_path):
    """expected_days defaulting to 0 would make every year trivially complete."""
    _fetch_year(tmp_path, 2017)
    (tmp_path / "_manifests" / "2017.json").write_text("{trunc", encoding="utf-8")
    assert read_manifest(tmp_path, 2017) is None
    assert govinfo_range_usable(tmp_path, 2017, 2017) == (False, [2017])


def test_coverage_report_shows_the_shortfall(tmp_path):
    _fetch_year(tmp_path, 2017, expected=SESSION_DAYS, fetched=22, phantom=1)
    cov = coverage_report(tmp_path, 2017, 2017)[2017]
    assert (cov.expected, cov.fetched, cov.phantom, cov.accounted) == (30, 22, 1, 23)
    assert cov.complete is False
    assert "23/30" in cov.describe()


def test_real_day_counts_reports_every_year_in_range(tmp_path):
    _write_day(tmp_path, 2018, "CREC-2018-01-03", [{"text": "china"}])
    _write_phantom(tmp_path, 2018, "CREC-2018-01-04")
    assert real_day_counts(tmp_path, 2017, 2019) == {2017: 0, 2018: 1, 2019: 0}


def test_min_days_floor_is_not_silently_zero():
    """Used as a plausibility bound on the manifest itself."""
    assert MIN_REAL_DAYS_PER_YEAR >= 20
