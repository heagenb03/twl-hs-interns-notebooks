# scripts/tests/test_calibration_years.py
"""The splice verdict is computed on a SAMPLE of the overlap, not all of it.

Pulling every GovInfo year in 1994-2016 costs ~32 hours serial and exists
purely to calibrate -- none of it reaches a published CSV, because Gentzkow
supplies every pre-2017 count. 2010-2016 is different: build_congress_senators
needs it for the bioguide roster and the serving set, so it is data, not just
calibration.

So the calibration set is 2010-2016 in full plus sparse probes across
1994-2009. That choice is deliberate and the shape matters:

  * SPARSE, NOT SHORT. A contiguous 2010-2016 window would be cheaper still,
    but the scale factor is applied to all of 1990-2016, and a factor fitted
    only to the last seven years of the overlap extrapolates backwards with
    nothing testing it. The probes keep the calibration SPANNING the era the
    factor is applied to, which is what cv is supposed to measure -- whether
    the two corpora track each other, not merely whether they agree once.
  * The probes are what make a drift detectable. If the Gentzkow/GovInfo
    relationship in 1994 differs from 2016, cv rises and the verdict moves to
    govinfo_only rather than silently scaling the 1990s by a 2010s factor.
"""
import pytest

import calibrate_splice
from calibrate_splice import (
    CALIBRATION_YEARS,
    OVERLAP_END_YEAR,
    OVERLAP_START_YEAR,
)


def test_calibration_years_span_the_whole_overlap():
    """A short recent window would extrapolate; a spanning sample does not."""
    assert min(CALIBRATION_YEARS) <= OVERLAP_START_YEAR + 1
    assert max(CALIBRATION_YEARS) == OVERLAP_END_YEAR


def test_calibration_years_include_every_senator_roster_year_in_the_overlap():
    """2010-2016 is needed for the roster and serving set regardless, so it is
    free to calibrate on and must not be sampled away."""
    from twl_common import SENATOR_YEARS

    roster_years = [y for y in SENATOR_YEARS if y <= OVERLAP_END_YEAR]
    assert set(roster_years) <= set(CALIBRATION_YEARS)


def test_calibration_probes_reach_back_into_the_1990s():
    """Without a pre-2000 probe, a 1990s-specific divergence is invisible."""
    assert any(y < 2000 for y in CALIBRATION_YEARS)


def test_calibration_years_are_sorted_and_unique():
    assert list(CALIBRATION_YEARS) == sorted(set(CALIBRATION_YEARS))


def test_calibration_years_stay_inside_the_overlap():
    """A year outside the overlap has no Gentzkow counterpart to compare to."""
    for year in CALIBRATION_YEARS:
        assert OVERLAP_START_YEAR <= year <= OVERLAP_END_YEAR


def test_enough_points_for_a_meaningful_spread():
    """cv over three points is not a stability measurement."""
    assert len(CALIBRATION_YEARS) >= 8


def test_the_sample_is_a_real_saving():
    """If this stops being much cheaper than the full overlap, drop the
    complexity and pull everything."""
    full = OVERLAP_END_YEAR - OVERLAP_START_YEAR + 1
    assert len(CALIBRATION_YEARS) <= full * 0.6


# --- the gate and the verdict must both use exactly this set ---------------


def test_completeness_gate_checks_only_the_calibration_years(tmp_path, monkeypatch):
    """Pulling 1995 is not required, so its absence must not block the verdict."""
    import json

    from congress_cache import write_manifest

    govinfo, gentzkow = tmp_path / "gov", tmp_path / "gen"
    gentzkow.mkdir()

    for year in CALIBRATION_YEARS:
        packages = [f"CREC-{year}-{i:03d}" for i in range(30)]
        write_manifest(govinfo, year, packages)
        year_dir = govinfo / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        for pkg in packages:
            (year_dir / f"{pkg}.json").write_text(
                json.dumps({"package": pkg, "granules": [{"text": "china"}]}),
                encoding="utf-8",
            )

    with (gentzkow / "speeches_senate_100.jsonl").open("w", encoding="utf-8") as fh:
        for year in CALIBRATION_YEARS:
            for i in range(calibrate_splice.MIN_GENTZKOW_SPEECHES_PER_YEAR):
                fh.write(
                    json.dumps(
                        {"date": f"{year}0104", "text": "china", "speech_id": f"{year}{i}"}
                    )
                    + "\n"
                )

    # Years like 1995 are absent entirely. That must be fine.
    calibrate_splice.require_complete_overlap(gentzkow, govinfo)


def test_a_missing_calibration_year_still_blocks_the_verdict(tmp_path):
    """Sampling narrows WHICH years are required; it does not make any of the
    ones that remain optional."""
    import json

    from congress_cache import write_manifest

    govinfo, gentzkow = tmp_path / "gov", tmp_path / "gen"
    gentzkow.mkdir()
    dropped = CALIBRATION_YEARS[0]

    for year in CALIBRATION_YEARS:
        if year == dropped:
            continue
        packages = [f"CREC-{year}-{i:03d}" for i in range(30)]
        write_manifest(govinfo, year, packages)
        year_dir = govinfo / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        for pkg in packages:
            (year_dir / f"{pkg}.json").write_text(
                json.dumps({"package": pkg, "granules": [{"text": "china"}]}),
                encoding="utf-8",
            )

    with (gentzkow / "speeches_senate_100.jsonl").open("w", encoding="utf-8") as fh:
        for year in CALIBRATION_YEARS:
            for i in range(calibrate_splice.MIN_GENTZKOW_SPEECHES_PER_YEAR):
                fh.write(
                    json.dumps(
                        {"date": f"{year}0104", "text": "china", "speech_id": f"{year}{i}"}
                    )
                    + "\n"
                )

    with pytest.raises(calibrate_splice.OverlapIncompleteError) as exc:
        calibrate_splice.require_complete_overlap(gentzkow, govinfo)
    assert str(dropped) in str(exc.value)
